"""
Models package
Import all models here for easy access and Alembic auto-detection
"""

from app.models.user import User, UserRole
from app.models.chat import Chat, ChatMode, ChatChannel
from app.models.message import Message, MessageSender, MessageStatus
from app.models.admin_message import AdminMessage
from app.models.ticket import Ticket, TicketStatus, TicketPriority
from app.models.agent_profile import AgentProfile, AgentStatus
from app.models.queue_assignment import QueueAssignment, AssignmentType
from app.models.agent_metrics import AgentMetrics

__all__ = [
    # User
    "User",
    "UserRole",
    # Chat
    "Chat",
    "ChatMode",
    "ChatChannel",
    # Message
    "Message",
    "MessageSender",
    "MessageStatus",
    # Admin Message
    "AdminMessage",
    # Ticket System
    "Ticket",
    "TicketStatus",
    "TicketPriority",
    # Agent Profile
    "AgentProfile",
    "AgentStatus",
    # Queue
    "QueueAssignment",
    "AssignmentType",
    # Metrics
    "AgentMetrics",
]
