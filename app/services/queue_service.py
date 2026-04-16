"""
Queue Service - Ticket Assignment & Queue Management
Handles automatic assignment of tickets to agents using FCFS (First Come First Serve)
"""

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func
from datetime import datetime
from typing import Optional, List

from app.models.ticket import Ticket, TicketStatus, TicketPriority
from app.models.agent_profile import AgentProfile, AgentStatus
from app.models.queue_assignment import QueueAssignment, AssignmentType
from app.models.chat import Chat, ChatMode
from app.models.user import User, UserRole


class QueueService:
    """Service untuk manage ticket queue dan assignment"""

    def __init__(self, db: Session):
        self.db = db

    def create_ticket_for_chat(
        self,
        chat_id: int,
        priority: TicketPriority = TicketPriority.medium,
        auto_assign: bool = True
    ) -> Ticket:
        """
        Buat ticket baru untuk chat
        Args:
            chat_id: ID dari chat
            priority: Priority ticket (default: medium)
            auto_assign: Apakah auto-assign ke agent yang available
        Returns:
            Ticket object yang baru dibuat
        """
        # Cek apakah chat sudah punya ticket
        existing_ticket = self.db.query(Ticket).filter(Ticket.chat_id == chat_id).first()
        if existing_ticket:
            return existing_ticket

        # Buat ticket baru
        ticket = Ticket(
            chat_id=chat_id,
            status=TicketStatus.pending,
            priority=priority
        )
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)

        # Auto-assign jika diminta
        if auto_assign:
            self.auto_assign_ticket(ticket.id)

        return ticket

    def get_available_agents(self) -> List[AgentProfile]:
        """
        Dapatkan list agent yang available untuk terima ticket baru
        Sorted by priority_score (descending) and last_activity_at (ascending)

        Returns:
            List of AgentProfile yang available
        """
        return self.db.query(AgentProfile).filter(
            and_(
                AgentProfile.is_available == True,
                AgentProfile.status == AgentStatus.online
            )
        ).order_by(
            AgentProfile.priority_score.desc(),
            AgentProfile.last_activity_at.asc().nullsfirst()
        ).all()

    def get_agent_active_ticket_count(self, agent_id: int) -> int:
        """
        Hitung berapa ticket aktif yang sedang dihandle agent

        Args:
            agent_id: User ID dari agent
        Returns:
            Jumlah ticket aktif
        """
        count = self.db.query(func.count(Ticket.id)).filter(
            and_(
                Ticket.assigned_agent_id == agent_id,
                or_(
                    Ticket.status == TicketStatus.assigned,
                    Ticket.status == TicketStatus.in_progress,
                    Ticket.status == TicketStatus.waiting_customer
                )
            )
        ).scalar()
        return count or 0

    def find_best_agent_fcfs(self) -> Optional[User]:
        """
        Cari agent terbaik untuk assignment menggunakan algoritma FCFS

        Kriteria:
        1. Agent harus online dan available
        2. Belum mencapai max concurrent tickets
        3. Priority berdasarkan:
           - Least active tickets (paling sedikit ticket aktif)
           - Highest priority_score
           - Earliest last_activity (yang paling lama idle)

        Returns:
            User object dari agent yang dipilih, atau None jika tidak ada
        """
        available_agents = self.get_available_agents()

        best_agent = None
        min_active_tickets = float('inf')

        for agent_profile in available_agents:
            active_count = self.get_agent_active_ticket_count(agent_profile.user_id)

            # Skip jika sudah full capacity
            if active_count >= agent_profile.max_concurrent_tickets:
                continue

            # FCFS: pilih yang paling sedikit ticket aktif
            if active_count < min_active_tickets:
                min_active_tickets = active_count
                best_agent = agent_profile.user

        return best_agent

    def auto_assign_ticket(self, ticket_id: int) -> bool:
        """
        Auto-assign ticket ke agent yang available menggunakan FCFS

        Args:
            ticket_id: ID ticket yang akan di-assign
        Returns:
            True jika berhasil assign, False jika tidak ada agent available
        """
        ticket = self.db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            return False

        # Skip jika sudah di-assign
        if ticket.status != TicketStatus.pending:
            return False

        # Cari agent terbaik
        best_agent = self.find_best_agent_fcfs()
        if not best_agent:
            # Tidak ada agent available
            return False

        # Assign ticket ke agent
        now = datetime.now()
        ticket.assigned_agent_id = best_agent.id
        ticket.status = TicketStatus.assigned
        ticket.assigned_at = now

        # Update chat mode ke agent
        chat = self.db.query(Chat).filter(Chat.id == ticket.chat_id).first()
        if chat:
            chat.mode = ChatMode.agent
            chat.assigned_agent_id = best_agent.id

        # Create assignment record
        assignment = QueueAssignment(
            ticket_id=ticket.id,
            agent_id=best_agent.id,
            assignment_type=AssignmentType.auto,
            assigned_at=now,
            is_active=True,
            reason="Auto-assigned via FCFS algorithm"
        )
        self.db.add(assignment)

        # Update agent profile
        agent_profile = self.db.query(AgentProfile).filter(
            AgentProfile.user_id == best_agent.id
        ).first()
        if agent_profile:
            agent_profile.last_activity_at = now
            agent_profile.total_tickets_handled += 1

        self.db.commit()
        return True

    def manual_assign_ticket(
        self,
        ticket_id: int,
        agent_id: int,
        assigned_by_id: int,
        reason: Optional[str] = None
    ) -> bool:
        """
        Manual assign ticket ke agent tertentu (by admin)

        Args:
            ticket_id: ID ticket
            agent_id: ID agent yang akan menerima ticket
            assigned_by_id: ID admin yang melakukan assignment
            reason: Alasan assignment
        Returns:
            True jika berhasil
        """
        ticket = self.db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            return False

        agent = self.db.query(User).filter(User.id == agent_id).first()
        if not agent:
            return False

        now = datetime.now()

        # Deactivate previous assignment jika ada
        if ticket.assigned_agent_id:
            prev_assignment = self.db.query(QueueAssignment).filter(
                and_(
                    QueueAssignment.ticket_id == ticket.id,
                    QueueAssignment.is_active == True
                )
            ).first()
            if prev_assignment:
                prev_assignment.is_active = False
                prev_assignment.unassigned_at = now

        # Assign to new agent
        ticket.assigned_agent_id = agent_id
        ticket.status = TicketStatus.assigned
        if not ticket.assigned_at:  # Only set if first time
            ticket.assigned_at = now

        # Update chat
        chat = self.db.query(Chat).filter(Chat.id == ticket.chat_id).first()
        if chat:
            chat.mode = ChatMode.agent
            chat.assigned_agent_id = agent_id

        # Create assignment record
        assignment = QueueAssignment(
            ticket_id=ticket.id,
            agent_id=agent_id,
            assignment_type=AssignmentType.manual,
            assigned_by_id=assigned_by_id,
            assigned_at=now,
            is_active=True,
            reason=reason or "Manual assignment by admin"
        )
        self.db.add(assignment)

        # Update agent profile
        agent_profile = self.db.query(AgentProfile).filter(
            AgentProfile.user_id == agent_id
        ).first()
        if agent_profile:
            agent_profile.last_activity_at = now
            agent_profile.total_tickets_handled += 1

        self.db.commit()
        return True

    def agent_claim_ticket(self, ticket_id: int, agent_id: int) -> bool:
        """
        Agent mengklaim ticket dari queue (self-assignment)

        Args:
            ticket_id: ID ticket
            agent_id: ID agent yang claim
        Returns:
            True jika berhasil claim
        """
        ticket = self.db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket or ticket.status != TicketStatus.pending:
            return False

        # Cek apakah agent available dan belum full capacity
        agent_profile = self.db.query(AgentProfile).filter(
            AgentProfile.user_id == agent_id
        ).first()

        if not agent_profile or not agent_profile.can_accept_ticket:
            return False

        active_count = self.get_agent_active_ticket_count(agent_id)
        if active_count >= agent_profile.max_concurrent_tickets:
            return False

        now = datetime.now()

        # Assign
        ticket.assigned_agent_id = agent_id
        ticket.status = TicketStatus.assigned
        ticket.assigned_at = now

        # Update chat
        chat = self.db.query(Chat).filter(Chat.id == ticket.chat_id).first()
        if chat:
            chat.mode = ChatMode.agent
            chat.assigned_agent_id = agent_id

        # Create assignment record
        assignment = QueueAssignment(
            ticket_id=ticket.id,
            agent_id=agent_id,
            assignment_type=AssignmentType.claimed,
            assigned_at=now,
            is_active=True,
            reason="Agent claimed from queue"
        )
        self.db.add(assignment)

        # Update agent profile
        agent_profile.last_activity_at = now
        agent_profile.total_tickets_handled += 1

        self.db.commit()
        return True

    def get_pending_tickets(self, limit: int = 50) -> List[Ticket]:
        """
        Dapatkan list ticket yang masih pending (belum di-assign)
        Sorted by priority (urgent first) and created_at (oldest first - FCFS)

        Args:
            limit: Maksimal berapa ticket yang direturn
        Returns:
            List of Ticket
        """
        priority_order = {
            TicketPriority.urgent: 1,
            TicketPriority.high: 2,
            TicketPriority.medium: 3,
            TicketPriority.low: 4
        }

        tickets = self.db.query(Ticket).options(
            joinedload(Ticket.assigned_agent),
            joinedload(Ticket.chat)
        ).filter(
            Ticket.status == TicketStatus.pending
        ).order_by(
            Ticket.priority,  # Will use enum order
            Ticket.created_at.asc()  # FCFS - oldest first
        ).limit(limit).all()

        return tickets

    def transfer_ticket(
        self,
        ticket_id: int,
        from_agent_id: Optional[int],
        to_agent_id: int,
        reason: Optional[str] = None
    ) -> bool:
        """
        Transfer ticket dari satu agent ke agent lain

        Args:
            ticket_id: ID ticket yang akan ditransfer
            from_agent_id: ID agent yang saat ini memegang ticket
            to_agent_id: ID agent tujuan
            reason: Alasan transfer
        Returns:
            True jika berhasil
        """
        ticket = self.db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            return False

        # Verifikasi ownership hanya jika from_agent_id diberikan dan ticket memang sudah assigned
        if (
            from_agent_id is not None
            and ticket.assigned_agent_id is not None
            and ticket.assigned_agent_id != from_agent_id
        ):
            return False

        to_agent = self.db.query(User).filter(User.id == to_agent_id).first()
        if not to_agent or to_agent.role != UserRole.agent:
            return False

        # Pastikan agent tujuan sedang online dan available
        to_agent_profile = self.db.query(AgentProfile).filter(
            AgentProfile.user_id == to_agent_id
        ).first()
        if not to_agent_profile or to_agent_profile.status != AgentStatus.online or not to_agent_profile.is_available:
            return False

        now = datetime.now()

        # Deactivate assignment lama
        prev_assignment = self.db.query(QueueAssignment).filter(
            and_(
                QueueAssignment.ticket_id == ticket.id,
                QueueAssignment.is_active == True
            )
        ).first()
        if prev_assignment:
            prev_assignment.is_active = False
            prev_assignment.unassigned_at = now

        # Update ticket ke agent baru
        ticket.assigned_agent_id = to_agent_id
        ticket.status = TicketStatus.assigned

        # Update chat
        chat = self.db.query(Chat).filter(Chat.id == ticket.chat_id).first()
        if chat:
            chat.assigned_agent_id = to_agent_id

        # Buat assignment record baru (type: transferred)
        new_assignment = QueueAssignment(
            ticket_id=ticket.id,
            agent_id=to_agent_id,
            assignment_type=AssignmentType.transferred,
            assigned_by_id=from_agent_id,
            assigned_at=now,
            is_active=True,
            reason=reason or f"Transferred by agent #{from_agent_id}"
        )
        self.db.add(new_assignment)

        # Update stats agent baru
        to_agent_profile = self.db.query(AgentProfile).filter(
            AgentProfile.user_id == to_agent_id
        ).first()
        if to_agent_profile:
            to_agent_profile.last_activity_at = now
            to_agent_profile.total_tickets_handled += 1

        self.db.commit()
        return True

    def get_ticket_by_chat_id(self, chat_id: int) -> Optional[Ticket]:
        """Cari ticket berdasarkan chat_id"""
        return self.db.query(Ticket).filter(Ticket.chat_id == chat_id).first()

    def resolve_ticket(self, ticket_id: int) -> bool:
        """
        Mark ticket sebagai resolved

        Args:
            ticket_id: ID ticket
        Returns:
            True jika berhasil
        """
        ticket = self.db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            return False

        now = datetime.now()
        ticket.status = TicketStatus.resolved
        ticket.resolved_at = now

        # Update chat mode ke closed
        chat = self.db.query(Chat).filter(Chat.id == ticket.chat_id).first()
        if chat:
            chat.mode = ChatMode.closed

        # Deactivate assignment
        assignment = self.db.query(QueueAssignment).filter(
            and_(
                QueueAssignment.ticket_id == ticket.id,
                QueueAssignment.is_active == True
            )
        ).first()
        if assignment:
            assignment.is_active = False
            assignment.unassigned_at = now

        # Update agent stats
        if ticket.assigned_agent_id:
            agent_profile = self.db.query(AgentProfile).filter(
                AgentProfile.user_id == ticket.assigned_agent_id
            ).first()
            if agent_profile:
                agent_profile.total_tickets_resolved += 1

        self.db.commit()
        return True
