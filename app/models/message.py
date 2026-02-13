from sqlalchemy import Column, Integer, String, DateTime, Text, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.config.database import Base
import enum


class MessageSender(enum.Enum):
    customer = "customer"
    agent = "agent"


class MessageStatus(enum.Enum):
    sent = "sent"
    read = "read"


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)

    text = Column(Text, nullable=False)
    sender = Column(Enum(MessageSender, name="message_sender"), nullable=False)
    status = Column(Enum(MessageStatus, name="message_status"), nullable=False, default=MessageStatus.sent)

    # For agent messages, track which agent sent it
    agent_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    agent = relationship("User", backref="sent_messages")

    # Media attachment fields
    media_url = Column(String, nullable=True)       # Relative path to uploaded file
    media_type = Column(String, nullable=True)      # "image", "video", "document", "audio"
    media_filename = Column(String, nullable=True)  # Original filename

    # For group messages, track who sent the message (participant)
    participant_phone = Column(String, nullable=True)  # Phone number of sender in group
    participant_name = Column(String, nullable=True)   # Name of sender in group

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship back to chat
    chat = relationship("Chat", back_populates="messages")
