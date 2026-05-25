"""
Ticket & Queue Management Routes
Endpoints untuk manage tickets, queue, dan assignment
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.config.deps import get_db, get_current_user
from app.models.user import User, UserRole
from app.models.ticket import Ticket, TicketStatus, TicketPriority
from app.models.queue_assignment import QueueAssignment
from app.models.agent_profile import AgentProfile, AgentStatus
from app.services.queue_service import QueueService
from app.services.ws_manager import manager

router = APIRouter(prefix="/tickets", tags=["tickets"])


# Pydantic schemas untuk request/response
class TicketResponse(BaseModel):
    id: int
    chat_id: int
    status: str
    priority: str
    assigned_agent_id: Optional[int]
    created_at: datetime
    assigned_at: Optional[datetime]
    first_response_at: Optional[datetime]
    resolved_at: Optional[datetime]
    notes: Optional[str]
    tags: Optional[str]

    # Chat info
    customer_name: Optional[str]
    customer_phone: Optional[str]

    # Agent info
    agent_name: Optional[str]

    class Config:
        from_attributes = True


class AssignTicketRequest(BaseModel):
    agent_id: int
    reason: Optional[str] = None


class TransferTicketRequest(BaseModel):
    to_agent_id: int
    reason: Optional[str] = None


class UpdateTicketStatusRequest(BaseModel):
    status: TicketStatus


class UpdateTicketPriorityRequest(BaseModel):
    priority: TicketPriority


class TicketStatsResponse(BaseModel):
    total_pending: int
    total_assigned: int
    total_in_progress: int
    total_waiting_customer: int
    total_resolved_today: int
    total_resolved: int
    total_escalated: int
    avg_wait_time_seconds: Optional[float]
    avg_resolution_time_seconds: Optional[float]


# Helper functions
def ticket_to_response(ticket: Ticket) -> dict:
    """Convert Ticket model to response dict"""
    return {
        "id": ticket.id,
        "chat_id": ticket.chat_id,
        "status": ticket.status.value,
        "priority": ticket.priority.value,
        "assigned_agent_id": ticket.assigned_agent_id,
        "created_at": ticket.created_at,
        "assigned_at": ticket.assigned_at,
        "first_response_at": ticket.first_response_at,
        "resolved_at": ticket.resolved_at,
        "notes": ticket.notes,
        "tags": ticket.tags,
        "customer_name": ticket.chat.customer_name if ticket.chat else None,
        "customer_phone": ticket.chat.customer_phone if ticket.chat else None,
        "agent_name": ticket.assigned_agent.name if ticket.assigned_agent else None,
    }


# Endpoints
@router.get("/online-agents")
def get_online_agents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Dapatkan daftar agent yang sedang online dan available.
    Digunakan untuk dropdown pilihan tujuan transfer chat.
    Agent yang login tidak akan muncul dalam daftar (tidak bisa transfer ke diri sendiri).
    """
    profiles = db.query(AgentProfile).filter(
        AgentProfile.status == AgentStatus.online,
        AgentProfile.is_available == True
    ).all()

    result = []
    for profile in profiles:
        # Exclude diri sendiri
        if profile.user_id == current_user.id:
            continue
        result.append({
            "agent_id": profile.user_id,
            "name": profile.user.name,
            "display_name": profile.display_name,
            "status": profile.status.value,
            "is_available": profile.is_available,
        })

    return result


@router.get("/queue", response_model=List[TicketResponse])
def get_pending_tickets(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of pending tickets in queue (FCFS order)
    Available for all agents and admins
    """
    queue_service = QueueService(db)
    tickets = queue_service.get_pending_tickets(limit=limit)

    return [ticket_to_response(ticket) for ticket in tickets]


@router.get("/my-tickets", response_model=List[TicketResponse])
def get_my_tickets(
    status: Optional[TicketStatus] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get tickets assigned to current agent
    Filter by status if provided
    """
    query = db.query(Ticket).options(
        joinedload(Ticket.assigned_agent),
        joinedload(Ticket.chat)
    ).filter(Ticket.assigned_agent_id == current_user.id)

    if status:
        query = query.filter(Ticket.status == status)

    tickets = query.order_by(Ticket.created_at.desc()).all()

    return [ticket_to_response(ticket) for ticket in tickets]


@router.get("/all", response_model=List[TicketResponse])
def get_all_tickets(
    status: Optional[TicketStatus] = None,
    priority: Optional[TicketPriority] = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all tickets (admin only)
    Filter by status and/or priority
    """
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view all tickets"
        )

    query = db.query(Ticket).options(
        joinedload(Ticket.assigned_agent),
        joinedload(Ticket.chat)
    )

    if status:
        query = query.filter(Ticket.status == status)

    if priority:
        query = query.filter(Ticket.priority == priority)

    tickets = query.order_by(Ticket.created_at.desc()).limit(limit).all()

    return [ticket_to_response(ticket) for ticket in tickets]


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get specific ticket by ID"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Check permission: agent can only see their own tickets
    if current_user.role == UserRole.agent:
        if ticket.assigned_agent_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your assigned tickets"
            )

    return ticket_to_response(ticket)


@router.post("/{ticket_id}/claim")
def claim_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Agent claims a ticket from the queue (self-assignment)
    """
    if current_user.role != UserRole.agent:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only agents can claim tickets"
        )

    queue_service = QueueService(db)
    success = queue_service.agent_claim_ticket(ticket_id, current_user.id)

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Cannot claim ticket (already assigned, at capacity, or not available)"
        )

    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

    return {
        "status": "success",
        "message": f"Ticket {ticket_id} claimed successfully",
        "ticket": ticket_to_response(ticket)
    }


@router.post("/{ticket_id}/assign")
def assign_ticket(
    ticket_id: int,
    request: AssignTicketRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Manually assign ticket to specific agent (admin only)
    """
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can manually assign tickets"
        )

    queue_service = QueueService(db)
    success = queue_service.manual_assign_ticket(
        ticket_id=ticket_id,
        agent_id=request.agent_id,
        assigned_by_id=current_user.id,
        reason=request.reason
    )

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Cannot assign ticket (ticket or agent not found)"
        )

    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

    return {
        "status": "success",
        "message": f"Ticket {ticket_id} assigned to agent {request.agent_id}",
        "ticket": ticket_to_response(ticket)
    }


@router.post("/{ticket_id}/transfer")
async def transfer_ticket(
    ticket_id: int,
    request: TransferTicketRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Agent mentransfer ticket ke agent lain.
    Hanya agent yang saat ini memegang ticket (atau admin) yang bisa transfer.
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Permission: agent hanya bisa transfer ticket miliknya, admin bisa transfer semua
    if current_user.role == UserRole.agent:
        if ticket.assigned_agent_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only transfer your own assigned tickets"
            )

    if request.to_agent_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Cannot transfer ticket to yourself"
        )

    queue_service = QueueService(db)
    from_agent_id = ticket.assigned_agent_id
    chat_id = ticket.chat_id
    success = queue_service.transfer_ticket(
        ticket_id=ticket_id,
        from_agent_id=from_agent_id,
        to_agent_id=request.to_agent_id,
        reason=request.reason
    )

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Tidak bisa transfer ticket: agent tujuan tidak ditemukan atau sedang tidak online/available"
        )

    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

    await manager.broadcast_global({
        "type": "ticket_transferred",
        "to_agent_id": request.to_agent_id,
        "from_agent_id": from_agent_id,
        "ticket_id": ticket_id,
        "chat_id": chat_id,
    })

    return {
        "status": "success",
        "message": f"Ticket {ticket_id} transferred to agent {request.to_agent_id}",
        "ticket": ticket_to_response(ticket)
    }


@router.post("/transfer-by-chat/{chat_id}")
async def transfer_ticket_by_chat(
    chat_id: int,
    request: TransferTicketRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Transfer ticket berdasarkan chat_id (lebih mudah digunakan dari frontend).
    Hanya agent yang memegang chat tersebut (atau admin) yang bisa transfer.
    """
    from app.models.chat import Chat

    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Permission check
    if current_user.role == UserRole.agent:
        if chat.assigned_agent_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only transfer chats assigned to you"
            )

    if request.to_agent_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Cannot transfer to yourself"
        )

    queue_service = QueueService(db)
    ticket = queue_service.get_ticket_by_chat_id(chat_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found for this chat")

    from_agent_id = ticket.assigned_agent_id
    ticket_id = ticket.id
    success = queue_service.transfer_ticket(
        ticket_id=ticket_id,
        from_agent_id=from_agent_id,
        to_agent_id=request.to_agent_id,
        reason=request.reason
    )

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Tidak bisa transfer chat: agent tujuan tidak ditemukan atau sedang tidak online/available"
        )

    db.refresh(ticket)

    await manager.broadcast_global({
        "type": "ticket_transferred",
        "to_agent_id": request.to_agent_id,
        "from_agent_id": from_agent_id,
        "ticket_id": ticket_id,
        "chat_id": chat_id,
    })

    return {
        "status": "success",
        "message": f"Chat {chat_id} transferred to agent {request.to_agent_id}",
        "ticket": ticket_to_response(ticket)
    }


@router.patch("/{ticket_id}/status")
def update_ticket_status(
    ticket_id: int,
    request: UpdateTicketStatusRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update ticket status
    Agent can update their own tickets, admin can update any
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Permission check
    if current_user.role == UserRole.agent:
        if ticket.assigned_agent_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your assigned tickets"
            )

    ticket.status = request.status

    # Set timestamps based on status
    if request.status == TicketStatus.resolved and not ticket.resolved_at:
        ticket.resolved_at = datetime.now()

    db.commit()
    db.refresh(ticket)

    return {
        "status": "success",
        "message": f"Ticket status updated to {request.status.value}",
        "ticket": ticket_to_response(ticket)
    }


@router.patch("/{ticket_id}/priority")
def update_ticket_priority(
    ticket_id: int,
    request: UpdateTicketPriorityRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update ticket priority (admin only)
    """
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update ticket priority"
        )

    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.priority = request.priority
    db.commit()
    db.refresh(ticket)

    return {
        "status": "success",
        "message": f"Ticket priority updated to {request.priority.value}",
        "ticket": ticket_to_response(ticket)
    }


@router.post("/{ticket_id}/resolve")
def resolve_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark ticket as resolved
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Permission check
    if current_user.role == UserRole.agent:
        if ticket.assigned_agent_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only resolve your assigned tickets"
            )

    queue_service = QueueService(db)
    success = queue_service.resolve_ticket(ticket_id)

    if not success:
        raise HTTPException(status_code=400, detail="Cannot resolve ticket")

    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

    return {
        "status": "success",
        "message": f"Ticket {ticket_id} marked as resolved",
        "ticket": ticket_to_response(ticket)
    }


@router.get("/stats/overview", response_model=TicketStatsResponse)
def get_ticket_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get overview statistics for tickets
    Admin: all tickets, Agent: their tickets only
    """
    from sqlalchemy import func
    from datetime import date

    query = db.query(Ticket)

    # Filter by agent if not admin
    if current_user.role == UserRole.agent:
        query = query.filter(Ticket.assigned_agent_id == current_user.id)

    # Count by status
    total_pending = query.filter(Ticket.status == TicketStatus.pending).count()
    total_assigned = query.filter(Ticket.status == TicketStatus.assigned).count()
    total_in_progress = query.filter(Ticket.status == TicketStatus.in_progress).count()
    total_waiting_customer = query.filter(Ticket.status == TicketStatus.waiting_customer).count()
    total_escalated = query.filter(Ticket.status == TicketStatus.escalated).count()

    # Resolved today
    today = date.today()
    total_resolved_today = query.filter(
        Ticket.status == TicketStatus.resolved,
        func.date(Ticket.resolved_at) == today
    ).count()

    # Total resolved (all time)
    total_resolved = query.filter(Ticket.status == TicketStatus.resolved).count()

    # Average times
    avg_wait_time = db.query(
        func.avg(func.extract('epoch', Ticket.assigned_at - Ticket.created_at))
    ).filter(Ticket.assigned_at.isnot(None)).scalar()

    avg_resolution_time = db.query(
        func.avg(func.extract('epoch', Ticket.resolved_at - Ticket.created_at))
    ).filter(Ticket.resolved_at.isnot(None)).scalar()

    return {
        "total_pending": total_pending,
        "total_assigned": total_assigned,
        "total_in_progress": total_in_progress,
        "total_waiting_customer": total_waiting_customer,
        "total_resolved_today": total_resolved_today,
        "total_resolved": total_resolved,
        "total_escalated": total_escalated,
        "avg_wait_time_seconds": float(avg_wait_time) if avg_wait_time else None,
        "avg_resolution_time_seconds": float(avg_resolution_time) if avg_resolution_time else None,
    }
