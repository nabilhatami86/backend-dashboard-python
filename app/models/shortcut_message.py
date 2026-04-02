from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.config.database import Base


class ShortcutMessage(Base):
    __tablename__ = "shortcut_messages"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, nullable=False, index=True)  # unique per user, not globally
    values = Column(Text, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("key", "created_by", name="uq_shortcut_key_per_user"),
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship to User
    creator = relationship("User", backref="shortcut_messages")
