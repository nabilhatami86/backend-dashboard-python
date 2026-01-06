from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.config.database import Base
import enum


class AssignmentType(enum.Enum):
    """Tipe assignment"""
    auto = "auto"          # Auto-assigned by system (FCFS)
    manual = "manual"      # Manual assignment by admin
    claimed = "claimed"    # Agent claimed dari queue
    transferred = "transferred"  # Transferred dari agent lain


class QueueAssignment(Base):
    """
    History assignment ticket ke agent
    Track siapa saja yang pernah handle ticket ini dan kenapa
    """
    __tablename__ = "queue_assignments"

    id = Column(Integer, primary_key=True, index=True)

    # References
    ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    ticket = relationship("Ticket", back_populates="assignments")

    agent_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    agent = relationship("User", foreign_keys=[agent_id])

    # Assignment info
    assignment_type = Column(Enum(AssignmentType, name="assignment_type"), nullable=False)
    assigned_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Siapa yang assign (jika manual)
    assigned_by = relationship("User", foreign_keys=[assigned_by_id])

    # Timestamps
    assigned_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    unassigned_at = Column(DateTime(timezone=True), nullable=True)  # Kapan di-release/transfer

    # Status
    is_active = Column(Boolean, default=True)  # False jika sudah ditransfer/release

    # Metadata
    reason = Column(String, nullable=True)  # Alasan assignment/transfer
    notes = Column(Text, nullable=True)

    @property
    def duration_seconds(self):
        """Berapa lama agent handle ticket ini"""
        if self.unassigned_at:
            return (self.unassigned_at - self.assigned_at).total_seconds()
        return (func.now() - self.assigned_at).total_seconds()
