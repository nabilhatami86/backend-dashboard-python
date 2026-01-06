from sqlalchemy import Column, Integer, DateTime, ForeignKey, Float, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.config.database import Base


class AgentMetrics(Base):
    """
    Daily metrics untuk monitoring agent performance
    Digunakan untuk dashboard monitoring
    """
    __tablename__ = "agent_metrics"

    id = Column(Integer, primary_key=True, index=True)

    # Reference
    agent_profile_id = Column(Integer, ForeignKey("agent_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_profile = relationship("AgentProfile", back_populates="metrics")

    # Date untuk daily metrics
    date = Column(Date, nullable=False, index=True, server_default=func.current_date())

    # Ticket metrics
    tickets_assigned = Column(Integer, default=0)  # Total ticket yang di-assign hari ini
    tickets_resolved = Column(Integer, default=0)  # Total ticket yang diselesaikan hari ini
    tickets_transferred = Column(Integer, default=0)  # Ticket yang ditransfer ke agent lain
    tickets_escalated = Column(Integer, default=0)  # Ticket yang di-eskalasi

    # Response time metrics (in seconds)
    avg_first_response_time = Column(Float, nullable=True)  # Average waktu first response
    avg_resolution_time = Column(Float, nullable=True)  # Average waktu resolve ticket
    avg_wait_time = Column(Float, nullable=True)  # Average waktu customer menunggu di-assign

    # Message metrics
    total_messages_sent = Column(Integer, default=0)  # Total pesan yang dikirim
    total_messages_received = Column(Integer, default=0)  # Total pesan yang diterima dari customer

    # Activity metrics
    active_hours = Column(Float, default=0.0)  # Total jam online hari ini
    total_online_duration_seconds = Column(Integer, default=0)  # Total detik online

    # Performance scores (calculated)
    satisfaction_score = Column(Float, nullable=True)  # Customer satisfaction (jika ada feedback)
    efficiency_score = Column(Float, nullable=True)  # Tickets resolved / tickets assigned

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    @property
    def resolution_rate(self):
        """Persentase ticket yang resolved dari yang di-assign"""
        if self.tickets_assigned == 0:
            return 0.0
        return (self.tickets_resolved / self.tickets_assigned) * 100

    @property
    def transfer_rate(self):
        """Persentase ticket yang ditransfer"""
        if self.tickets_assigned == 0:
            return 0.0
        return (self.tickets_transferred / self.tickets_assigned) * 100
