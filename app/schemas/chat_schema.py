from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ChatModeEnum(str, Enum):
    bot = "bot"
    agent = "agent"
    paused = "paused"
    closed = "closed"


class ChatChannelEnum(str, Enum):
    whatsapp = "WhatsApp"
    telegram = "Telegram"
    email = "Email"


class MessageSenderEnum(str, Enum):
    customer = "customer"
    agent = "agent"


class MessageStatusEnum(str, Enum):
    sent = "sent"
    read = "read"


# ============ MESSAGE SCHEMAS ============

class MessageCreate(BaseModel):
    chat_id: int
    text: str
    sender: MessageSenderEnum
    agent_id: Optional[int] = None
    # Media attachment fields
    media_url: Optional[str] = None
    media_type: Optional[str] = None       # "image", "video", "document", "audio"
    media_filename: Optional[str] = None


class MessageResponse(BaseModel):
    id: int
    text: str
    sender: MessageSenderEnum
    status: MessageStatusEnum
    time: str  # formatted time
    agent_id: Optional[int] = None
    # Media attachment fields
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    media_filename: Optional[str] = None
    # For group messages: info about who sent the message
    participant_phone: Optional[str] = None
    participant_name: Optional[str] = None

    class Config:
        from_attributes = True


# ============ CHAT SCHEMAS ============

class ChatCreate(BaseModel):
    customer_name: str
    customer_phone: str
    customer_email: Optional[str] = None
    customer_address: Optional[str] = None
    channel: ChatChannelEnum = ChatChannelEnum.whatsapp


class ChatUpdate(BaseModel):
    mode: Optional[ChatModeEnum] = None
    assigned_agent_id: Optional[int] = None
    online: Optional[bool] = None
    unread_count: Optional[int] = None
    priority: Optional[str] = None  # "low", "medium", "high"


class CustomerProfile(BaseModel):
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    lastActive: Optional[str] = None


class ChatResponse(BaseModel):
    id: int
    name: str
    channel: str
    online: bool
    unread: int
    mode: str
    profile: CustomerProfile
    messages: List[MessageResponse]
    # Group information (for WhatsApp group chats)
    group_id: Optional[str] = None
    group_name: Optional[str] = None
    # Transfer info: diisi saat chat baru saja ditransfer dari agent lain
    transfer_note: Optional[str] = None
    transfer_from_agent: Optional[str] = None
    # Ticket priority
    priority: Optional[str] = None

    class Config:
        from_attributes = True


class AssignedAgentInfo(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class ChatListResponse(BaseModel):
    id: int
    name: str
    channel: str
    online: bool
    unread: int
    mode: str
    last_message_at: datetime
    assigned_agent: Optional[AssignedAgentInfo] = None
    # Group information (for WhatsApp group chats)
    group_id: Optional[str] = None
    group_name: Optional[str] = None
    # Last participant info (for group chats - who sent last message)
    last_participant_name: Optional[str] = None
    priority: Optional[str] = None

    class Config:
        from_attributes = True
