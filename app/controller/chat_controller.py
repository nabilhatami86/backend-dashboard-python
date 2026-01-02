from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.chat import Chat, ChatMode
from app.models.message import Message, MessageSender, MessageStatus
from app.schemas.chat_schema import (
    ChatCreate,
    ChatUpdate,
    MessageCreate,
    ChatResponse,
    ChatListResponse,
    MessageResponse,
    CustomerProfile
)
from datetime import datetime
from typing import List


def get_all_chats(db: Session, user_id: int = None, user_role: str = None) -> List[ChatListResponse]:
    """Get all chats, optionally filtered by assigned agent"""
    query = db.query(Chat).order_by(desc(Chat.last_message_at))

    # If user is agent, only show assigned chats
    if user_role == "agent" and user_id:
        query = query.filter(Chat.assigned_agent_id == user_id)

    chats = query.all()

    result = []
    for chat in chats:
        result.append(ChatListResponse(
            id=chat.id,
            name=chat.customer_name,
            channel=chat.channel.value,
            online=chat.online,
            unread=chat.unread_count,
            mode=chat.mode.value,
            last_message_at=chat.last_message_at
        ))

    return result


def get_chat_detail(chat_id: int, db: Session) -> ChatResponse:
    """Get chat with all messages"""
    chat = db.query(Chat).filter(Chat.id == chat_id).first()

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found"
        )

    # Get all messages for this chat
    messages = db.query(Message).filter(
        Message.chat_id == chat_id
    ).order_by(Message.created_at).all()

    # Format messages
    formatted_messages = []
    for msg in messages:
        formatted_messages.append(MessageResponse(
            id=msg.id,
            text=msg.text,
            sender=msg.sender.value,
            status=msg.status.value,
            time=msg.created_at.strftime("%H:%M"),
            agent_id=msg.agent_id
        ))

    # Build customer profile
    profile = CustomerProfile(
        phone=chat.customer_phone,
        email=chat.customer_email,
        address=chat.customer_address,
        lastActive="Online" if chat.online else datetime.now().strftime("%Y-%m-%d %H:%M")
    )

    return ChatResponse(
        id=chat.id,
        name=chat.customer_name,
        channel=chat.channel.value,
        online=chat.online,
        unread=chat.unread_count,
        mode=chat.mode.value,
        profile=profile,
        messages=formatted_messages
    )


def create_chat(data: ChatCreate, db: Session) -> ChatResponse:
    """Create new chat"""
    # Check if chat with this phone already exists
    existing_chat = db.query(Chat).filter(
        Chat.customer_phone == data.customer_phone
    ).first()

    if existing_chat:
        # Return existing chat instead of creating duplicate
        return get_chat_detail(existing_chat.id, db)

    chat = Chat(
        customer_name=data.customer_name,
        customer_phone=data.customer_phone,
        customer_email=data.customer_email,
        customer_address=data.customer_address,
        channel=data.channel,
        mode=ChatMode.bot,
        online=True,
        unread_count=0
    )

    db.add(chat)
    db.commit()
    db.refresh(chat)

    return get_chat_detail(chat.id, db)


def update_chat(chat_id: int, data: ChatUpdate, db: Session) -> ChatResponse:
    """Update chat (mode, assigned agent, etc)"""
    chat = db.query(Chat).filter(Chat.id == chat_id).first()

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found"
        )

    if data.mode is not None:
        chat.mode = ChatMode[data.mode.value]

    if data.assigned_agent_id is not None:
        chat.assigned_agent_id = data.assigned_agent_id

    if data.online is not None:
        chat.online = data.online

    if data.unread_count is not None:
        chat.unread_count = data.unread_count

    db.commit()
    db.refresh(chat)

    return get_chat_detail(chat.id, db)


def send_message(data: MessageCreate, db: Session) -> MessageResponse:
    """Send a message in a chat"""
    from app.whapi.client import send_text
    import logging

    logger = logging.getLogger(__name__)

    chat = db.query(Chat).filter(Chat.id == data.chat_id).first()

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found"
        )

    message = Message(
        chat_id=data.chat_id,
        text=data.text,
        sender=MessageSender[data.sender.value],
        status=MessageStatus.sent,
        agent_id=data.agent_id if data.sender == "agent" else None
    )

    db.add(message)

    # Update chat's last_message_at
    chat.last_message_at = datetime.now()

    # If message from customer, increment unread count
    if data.sender == "customer":
        chat.unread_count += 1

    db.commit()
    db.refresh(message)

    # If message is from agent and chat is WhatsApp, send via WhatsApp API
    if data.sender == "agent" and chat.channel.value == "WhatsApp" and chat.customer_phone:
        try:
            result = send_text(chat.customer_phone, data.text)
            if result.get("ok"):
                logger.info(f"Message sent to WhatsApp for chat {chat.id}")
            else:
                logger.error(f"Failed to send WhatsApp message: {result.get('error')}")
        except Exception as e:
            logger.exception(f"Error sending WhatsApp message: {e}")
            # Don't fail the request if WhatsApp send fails

    return MessageResponse(
        id=message.id,
        text=message.text,
        sender=message.sender.value,
        status=message.status.value,
        time=message.created_at.strftime("%H:%M"),
        agent_id=message.agent_id
    )


def mark_messages_as_read(chat_id: int, db: Session):
    """Mark all messages in a chat as read"""
    chat = db.query(Chat).filter(Chat.id == chat_id).first()

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found"
        )

    # Mark all customer messages as read
    db.query(Message).filter(
        Message.chat_id == chat_id,
        Message.sender == MessageSender.customer,
        Message.status == MessageStatus.sent
    ).update({"status": MessageStatus.read})

    # Reset unread count
    chat.unread_count = 0

    db.commit()

    return {"message": "Messages marked as read"}


def delete_chat(chat_id: int, db: Session):
    """Delete a chat and all its messages"""
    chat = db.query(Chat).filter(Chat.id == chat_id).first()

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found"
        )

    # Delete all messages first (foreign key constraint)
    db.query(Message).filter(Message.chat_id == chat_id).delete()

    # Delete the chat
    db.delete(chat)
    db.commit()

    return {"message": "Chat deleted successfully"}


def update_message(message_id: int, new_text: str, db: Session):
    """Update/edit a message"""
    message = db.query(Message).filter(Message.id == message_id).first()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )

    # Only allow editing agent messages
    if message.sender != MessageSender.agent:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only edit agent messages"
        )

    message.text = new_text
    db.commit()
    db.refresh(message)

    return MessageResponse(
        id=message.id,
        text=message.text,
        sender=message.sender.value,
        status=message.status.value,
        time=message.created_at.strftime("%H:%M"),
        agent_id=message.agent_id
    )


def delete_message(message_id: int, db: Session):
    """Delete a message"""
    message = db.query(Message).filter(Message.id == message_id).first()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )

    # Only allow deleting agent messages
    if message.sender != MessageSender.agent:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only delete agent messages"
        )

    db.delete(message)
    db.commit()

    return {"message": "Message deleted successfully"}
