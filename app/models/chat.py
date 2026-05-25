from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.config.database import Base
import enum


class ChatMode(enum.Enum):
    bot = "bot"
    agent = "agent"
    paused = "paused"
    closed = "closed"


class ChatChannel(enum.Enum):
    whatsapp = "whatsapp"
    telegram = "telegram"
    email = "email"


class Chat(Base):
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String, nullable=False)
    customer_phone = Column(String, index=True)
    customer_email = Column(String, nullable=True)
    customer_address = Column(String, nullable=True)

    # Group information (for WhatsApp group messages)
    group_id = Column(String, nullable=True)  # WhatsApp group JID (e.g., 120363423035678646@g.us)
    group_name = Column(String, nullable=True)  # Group name for display
    last_participant_jid = Column(String, nullable=True)  # Last participant JID for auto-mention when replying

    channel = Column(Enum(ChatChannel, name="chat_channel"), nullable=False, default=ChatChannel.whatsapp)
    mode = Column(Enum(ChatMode, name="chat_mode"), nullable=False, default=ChatMode.bot)

    online = Column(Boolean, default=False)
    unread_count = Column(Integer, default=0)

    # Assigned agent (optional, nullable)
    assigned_agent_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    assigned_agent = relationship("User", backref="assigned_chats")

    last_message_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship to messages
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")

    # Relationship to ticket (one-to-one)
    ticket = relationship("Ticket", back_populates="chat", uselist=False, cascade="all, delete-orphan")

    priority = Column(Enum("low", "medium", "high", name="chat_priority"), default="medium")
