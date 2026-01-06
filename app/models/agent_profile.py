from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.config.database import Base
import enum


class AgentStatus(enum.Enum):
    """Status ketersediaan agent"""
    online = "online"
    offline = "offline"
    busy = "busy"
    break_time = "break"


class AgentProfile(Base):
    """
    Profile agent untuk multi-agent menggunakan 1 nomor WhatsApp yang sama
    Setiap agent punya profile sendiri walaupun pakai nomor yang sama
    """
    __tablename__ = "agent_profiles"

    id = Column(Integer, primary_key=True, index=True)

    # Reference to User
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    user = relationship("User", backref="agent_profile")

    # Agent identity untuk WhatsApp (signature/display name)
    display_name = Column(String, nullable=False)  # e.g., "Agent John", "CS Team A"
    signature = Column(String, nullable=True)  # Signature di akhir pesan, e.g., "-John"

    # Availability
    status = Column(Enum(AgentStatus, name="agent_status"), nullable=False, default=AgentStatus.offline)
    is_available = Column(Boolean, default=False)  # Apakah bisa terima ticket baru
    max_concurrent_tickets = Column(Integer, default=5)  # Maksimal ticket yang bisa dihandle bersamaan

    # Metadata
    expertise_tags = Column(String, nullable=True)  # Comma-separated, e.g., "billing,technical,sales"
    priority_score = Column(Integer, default=0)  # Untuk routing priority (semakin tinggi semakin prioritas)

    # Activity tracking
    last_activity_at = Column(DateTime(timezone=True), nullable=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # Stats (denormalized untuk performa)
    total_tickets_handled = Column(Integer, default=0)
    total_tickets_resolved = Column(Integer, default=0)
    average_response_time_seconds = Column(Integer, nullable=True)  # Average first response time
    average_resolution_time_seconds = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    metrics = relationship("AgentMetrics", back_populates="agent_profile", cascade="all, delete-orphan")

    @property
    def current_active_tickets(self):
        """Jumlah ticket yang sedang aktif (assigned/in_progress)"""
        from app.models.ticket import Ticket, TicketStatus
        from sqlalchemy import and_
        # This would need to be calculated via a query
        # Placeholder for demonstration
        return 0

    @property
    def is_at_capacity(self):
        """Apakah agent sudah mencapai max capacity"""
        return self.current_active_tickets >= self.max_concurrent_tickets

    @property
    def can_accept_ticket(self):
        """Apakah agent bisa menerima ticket baru"""
        return (
            self.is_available
            and self.status == AgentStatus.online
            and not self.is_at_capacity
        )
