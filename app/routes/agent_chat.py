"""
Agent Chat Routes
Endpoints untuk agent mengirim pesan ke customer via WhatsApp
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.config.deps import get_db, get_current_user
from app.models.user import User, UserRole
from app.models.chat import Chat, ChatMode
from app.models.message import Message, MessageSender, MessageStatus
from app.models.ticket import Ticket, TicketStatus
from app.whapi.client import send_text, send_media
from app.models.agent_profile import AgentProfile

router = APIRouter(prefix="/agent/chats", tags=["agent-chat"])


# Schemas
class SendMessageRequest(BaseModel):
    chat_id: int
    text: str
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    media_filename: Optional[str] = None


class MessageResponse(BaseModel):
    id: int
    chat_id: int
    text: str
    sender: str
    status: str
    agent_id: Optional[int]
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    media_filename: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatDetailResponse(BaseModel):
    id: int
    customer_name: str
    customer_phone: str
    mode: str
    online: bool
    unread_count: int
    last_message_at: Optional[datetime]
    ticket_id: Optional[int]
    ticket_status: Optional[str]
    ticket_priority: Optional[str]

    class Config:
        from_attributes = True


class AgentStatusUpdateRequest(BaseModel):
    is_available: bool
    status: str  # online, offline, busy, break


# Endpoints
@router.get("/my-chats", response_model=List[ChatDetailResponse])
def get_my_chats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all chats assigned to current agent
    """
    if current_user.role != UserRole.agent:
        raise HTTPException(status_code=403, detail="Only agents can access this endpoint")

    # Get chats assigned to this agent
    chats = db.query(Chat).filter(
        Chat.assigned_agent_id == current_user.id,
        Chat.mode == ChatMode.agent
    ).order_by(Chat.last_message_at.desc()).all()

    results = []
    for chat in chats:
        # Get ticket info
        ticket = db.query(Ticket).filter(Ticket.chat_id == chat.id).first()

        results.append({
            "id": chat.id,
            "customer_name": chat.customer_name,
            "customer_phone": chat.customer_phone,
            "mode": chat.mode.value,
            "online": chat.online,
            "unread_count": chat.unread_count,
            "last_message_at": chat.last_message_at,
            "ticket_id": ticket.id if ticket else None,
            "ticket_status": ticket.status.value if ticket else None,
            "ticket_priority": ticket.priority.value if ticket else None,
        })

    return results


@router.get("/chat/{chat_id}/messages", response_model=List[MessageResponse])
def get_chat_messages(
    chat_id: int,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get messages from a chat
    """
    if current_user.role != UserRole.agent:
        raise HTTPException(status_code=403, detail="Only agents can access this endpoint")

    # Verify chat is assigned to this agent
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    if chat.assigned_agent_id != current_user.id:
        raise HTTPException(status_code=403, detail="This chat is not assigned to you")

    # Get messages
    messages = db.query(Message).filter(
        Message.chat_id == chat_id
    ).order_by(Message.created_at.desc()).offset(offset).limit(limit).all()

    # Mark messages as read
    if messages:
        chat.unread_count = 0
        db.commit()

    return messages


@router.post("/send-message")
def send_message_to_customer(
    request: SendMessageRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Agent send message to customer via WhatsApp
    """
    if current_user.role != UserRole.agent:
        raise HTTPException(status_code=403, detail="Only agents can send messages")

    # Get chat
    chat = db.query(Chat).filter(Chat.id == request.chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Verify chat is assigned to this agent
    if chat.assigned_agent_id != current_user.id:
        raise HTTPException(status_code=403, detail="This chat is not assigned to you")

    # Get agent profile for signature
    agent_profile = db.query(AgentProfile).filter(
        AgentProfile.user_id == current_user.id
    ).first()

    # Prepare message text with agent signature
    message_text = request.text
    if agent_profile and agent_profile.signature:
        message_text = f"{request.text}\n\n{agent_profile.signature}"

    # Save message to database
    message = Message(
        chat_id=chat.id,
        text=request.text,  # Save original text without signature
        sender=MessageSender.agent,
        agent_id=current_user.id,
        status=MessageStatus.sent,
        created_at=datetime.now(),
        media_url=request.media_url,
        media_type=request.media_type,
        media_filename=request.media_filename,
    )
    db.add(message)

    # Update chat
    chat.last_message_at = datetime.now()

    # Update ticket first_response_at if this is first agent response
    ticket = db.query(Ticket).filter(Ticket.chat_id == chat.id).first()
    if ticket:
        if not ticket.first_response_at:
            ticket.first_response_at = datetime.now()

        # Update ticket status to in_progress if it's still assigned
        if ticket.status == TicketStatus.assigned:
            ticket.status = TicketStatus.in_progress

    db.commit()
    db.refresh(message)

    # Send to WhatsApp in background
    if request.media_url and request.media_type:
        target = f"{chat.customer_phone}@c.us"
        background_tasks.add_task(
            send_media, target, request.media_url, request.media_type,
            message_text, request.media_filename, None
        )
    else:
        background_tasks.add_task(send_text, chat.customer_phone, message_text)

    return {
        "status": "success",
        "message_id": message.id,
        "chat_id": chat.id,
        "sent_to_whatsapp": True,
        "message": message_text
    }


@router.patch("/status")
def update_agent_status(
    request: AgentStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update agent availability status
    """
    if current_user.role != UserRole.agent:
        raise HTTPException(status_code=403, detail="Only agents can update status")

    # Get agent profile
    agent_profile = db.query(AgentProfile).filter(
        AgentProfile.user_id == current_user.id
    ).first()

    if not agent_profile:
        raise HTTPException(status_code=404, detail="Agent profile not found")

    # Update status
    from app.models.agent_profile import AgentStatus

    try:
        agent_profile.is_available = request.is_available
        agent_profile.status = AgentStatus[request.status]
        agent_profile.last_activity_at = datetime.now()

        db.commit()
        db.refresh(agent_profile)

        return {
            "status": "success",
            "agent_id": current_user.id,
            "is_available": agent_profile.is_available,
            "status": agent_profile.status.value,
            "can_accept_ticket": agent_profile.can_accept_ticket
        }
    except KeyError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: online, offline, busy, break_time"
        )


@router.get("/status")
def get_agent_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current agent status and statistics
    """
    if current_user.role != UserRole.agent:
        raise HTTPException(status_code=403, detail="Only agents can access this endpoint")

    # Get agent profile
    agent_profile = db.query(AgentProfile).filter(
        AgentProfile.user_id == current_user.id
    ).first()

    if not agent_profile:
        raise HTTPException(status_code=404, detail="Agent profile not found")

    # Get active ticket count
    from app.services.queue_service import QueueService
    queue_service = QueueService(db)
    active_tickets = queue_service.get_agent_active_ticket_count(current_user.id)

    return {
        "agent_id": current_user.id,
        "name": current_user.name,
        "display_name": agent_profile.display_name,
        "status": agent_profile.status.value,
        "is_available": agent_profile.is_available,
        "can_accept_ticket": agent_profile.can_accept_ticket,
        "active_tickets": active_tickets,
        "max_concurrent_tickets": agent_profile.max_concurrent_tickets,
        "total_tickets_handled": agent_profile.total_tickets_handled,
        "total_tickets_resolved": agent_profile.total_tickets_resolved,
        "last_activity_at": agent_profile.last_activity_at,
    }


@router.post("/chat/{chat_id}/mark-waiting")
def mark_chat_waiting_customer(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark ticket as waiting for customer response
    """
    if current_user.role != UserRole.agent:
        raise HTTPException(status_code=403, detail="Only agents can update ticket status")

    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    if chat.assigned_agent_id != current_user.id:
        raise HTTPException(status_code=403, detail="This chat is not assigned to you")

    ticket = db.query(Ticket).filter(Ticket.chat_id == chat_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.status = TicketStatus.waiting_customer
    db.commit()

    return {
        "status": "success",
        "ticket_id": ticket.id,
        "new_status": ticket.status.value
    }


@router.post("/chat/{chat_id}/resolve")
def resolve_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Resolve ticket and close chat
    """
    if current_user.role != UserRole.agent:
        raise HTTPException(status_code=403, detail="Only agents can resolve tickets")

    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    if chat.assigned_agent_id != current_user.id:
        raise HTTPException(status_code=403, detail="This chat is not assigned to you")

    ticket = db.query(Ticket).filter(Ticket.chat_id == chat_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Use queue service to resolve
    from app.services.queue_service import QueueService
    queue_service = QueueService(db)
    success = queue_service.resolve_ticket(ticket.id)

    if not success:
        raise HTTPException(status_code=400, detail="Failed to resolve ticket")

    return {
        "status": "success",
        "ticket_id": ticket.id,
        "chat_id": chat_id,
        "resolved_at": ticket.resolved_at
    }
