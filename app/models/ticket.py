from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.config.database import Base
import enum


class TicketStatus(enum.Enum):
    """Status tiket dalam queue"""
    pending = "pending"              # Baru masuk, belum diambil agent
    assigned = "assigned"            # Sudah di-assign ke agent
    in_progress = "in_progress"      # Agent sedang handle
    waiting_customer = "waiting_customer"  # Menunggu response customer
    resolved = "resolved"            # Selesai
    escalated = "escalated"          # Di-eskalasi ke admin/supervisor
    closed = "closed"                # Ditutup


class TicketPriority(enum.Enum):
    """Priority tiket untuk queue ordering"""
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class Ticket(Base):
    """
    Model Ticket untuk queue management
    Setiap Chat yang mode=agent akan punya Ticket
    """
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)

    # Reference to Chat
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), unique=True, nullable=False)
    chat = relationship("Chat", back_populates="ticket")

    # Ticket info
    status = Column(Enum(TicketStatus, name="ticket_status"), nullable=False, default=TicketStatus.pending)
    priority = Column(Enum(TicketPriority, name="ticket_priority"), nullable=False, default=TicketPriority.medium)

    # Agent assignment
    assigned_agent_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    assigned_agent = relationship("User", foreign_keys=[assigned_agent_id], backref="assigned_tickets")

    # Timestamps untuk tracking
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    assigned_at = Column(DateTime(timezone=True), nullable=True)  # Kapan di-assign
    first_response_at = Column(DateTime(timezone=True), nullable=True)  # First response time
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Metadata
    notes = Column(Text, nullable=True)  # Internal notes untuk agent/admin
    tags = Column(String, nullable=True)  # Comma-separated tags untuk filtering

    # Relationships
    assignments = relationship("QueueAssignment", back_populates="ticket", cascade="all, delete-orphan")

    @property
    def wait_time_seconds(self):
        """Berapa lama customer menunggu (dari created sampai assigned)"""
        if self.assigned_at:
            return (self.assigned_at - self.created_at).total_seconds()
        return (func.now() - self.created_at).total_seconds()

    @property
    def response_time_seconds(self):
        """Berapa lama agent pertama kali response"""
        if self.first_response_at and self.assigned_at:
            return (self.first_response_at - self.assigned_at).total_seconds()
        return None

    @property
    def resolution_time_seconds(self):
        """Total waktu dari created sampai resolved"""
        if self.resolved_at:
            return (self.resolved_at - self.created_at).total_seconds()
        return None
