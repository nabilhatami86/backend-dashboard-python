from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
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
    CustomerProfile,
    AssignedAgentInfo
)
from datetime import datetime
from typing import List


def get_all_chats(db: Session, user_id: int = None, user_role: str = None) -> List[ChatListResponse]:
    query = db.query(Chat).options(
        joinedload(Chat.assigned_agent)
    ).order_by(desc(Chat.last_message_at))

    # Filter out CLOSED chats (these have resolved tickets, waiting for customer to restart)
    query = query.filter(Chat.mode != ChatMode.closed)

    # TICKET QUEUE SYSTEM: Agent can only see their assigned chats
    if user_role == "agent" and user_id:
        query = query.filter(Chat.assigned_agent_id == user_id)

    chats = query.all()

    result = []
    for chat in chats:
        assigned_agent = None
        if chat.assigned_agent:
            assigned_agent = AssignedAgentInfo(
                id=chat.assigned_agent.id,
                name=chat.assigned_agent.name
            )

        # Get last participant name for group chats
        last_participant_name = None
        if chat.group_id:
            last_customer_msg = db.query(Message).filter(
                Message.chat_id == chat.id,
                Message.sender == MessageSender.customer,
                Message.participant_name != None
            ).order_by(Message.created_at.desc()).first()
            if last_customer_msg:
                last_participant_name = last_customer_msg.participant_name

        result.append(ChatListResponse(
            id=chat.id,
            name=chat.customer_name,
            channel=chat.channel.value,
            online=chat.online,
            unread=chat.unread_count,
            mode=chat.mode.value,
            last_message_at=chat.last_message_at,
            assigned_agent=assigned_agent,
            group_id=chat.group_id,
            group_name=chat.group_name,
            last_participant_name=last_participant_name
        ))

    return result


def get_available_tickets(db: Session) -> List[ChatResponse]:
    query = db.query(Chat).filter(
        Chat.mode == ChatMode.paused,
        Chat.assigned_agent_id == None,
    ).order_by(Chat.last_message_at.asc())

    chats = query.all()

    result = []
    for chat in chats:
        # Get messages for this chat
        messages = db.query(Message).filter(Message.chat_id == chat.id).order_by(Message.created_at).all()

        message_responses = []
        for msg in messages:
            # Format time as HH:MM
            formatted_time = msg.created_at.strftime("%H:%M") if msg.created_at else "00:00"

            message_responses.append(MessageResponse(
                id=msg.id,
                text=msg.text,
                sender=msg.sender.value,
                status=msg.status.value,
                time=formatted_time,
                agent_id=msg.agent_id,
                media_url=msg.media_url,
                media_type=msg.media_type,
                media_filename=msg.media_filename,
                participant_phone=msg.participant_phone,
                participant_name=msg.participant_name
            ))

        # For group chats: customer_name is already participant name (set in webhook)
        # For private chats: customer_name is phone number or name
        result.append(ChatResponse(
            id=chat.id,
            name=chat.customer_name,
            channel=chat.channel.value,
            online=chat.online,
            unread=chat.unread_count,
            mode=chat.mode.value,
            profile=CustomerProfile(
                phone=chat.customer_phone,
                email=chat.customer_email,
                address=chat.customer_address,
                notes=None,
                lastActive=chat.last_message_at.isoformat() if chat.last_message_at else None
            ),
            messages=message_responses,
            group_id=chat.group_id,
            group_name=chat.group_name
        ))

    return result


def claim_ticket(chat_id: int, agent_id: int, db: Session) -> ChatResponse:
    from app.models.ticket import Ticket, TicketStatus, TicketPriority
    import logging

    logger = logging.getLogger(__name__)
    now = datetime.now()

    chat = db.query(Chat).filter(Chat.id == chat_id).first()

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found"
        )

    # Check if chat is already assigned
    if chat.assigned_agent_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Chat already assigned to agent {chat.assigned_agent_id}"
        )

    # Assign to agent and change mode
    chat.assigned_agent_id = agent_id
    chat.mode = ChatMode.agent

    # Update existing ticket or create new one
    existing_ticket = db.query(Ticket).filter(Ticket.chat_id == chat_id).first()
    if existing_ticket:
        existing_ticket.status = TicketStatus.in_progress
        existing_ticket.assigned_agent_id = agent_id
        existing_ticket.assigned_at = now
    else:
        new_ticket = Ticket(
            chat_id=chat_id,
            status=TicketStatus.in_progress,
            priority=TicketPriority.medium,
            assigned_agent_id=agent_id,
            assigned_at=now
        )
        db.add(new_ticket)

    db.commit()
    db.refresh(chat)

    return get_chat_detail(chat.id, db)


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
            agent_id=msg.agent_id,
            media_url=msg.media_url,
            media_type=msg.media_type,
            media_filename=msg.media_filename,
            participant_phone=msg.participant_phone,
            participant_name=msg.participant_name
        ))

    # Build customer profile
    profile = CustomerProfile(
        phone=chat.customer_phone,
        email=chat.customer_email,
        address=chat.customer_address,
        lastActive="Online" if chat.online else datetime.now().strftime("%Y-%m-%d %H:%M")
    )

    # For group chats: customer_name is already participant name (set in webhook)
    return ChatResponse(
        id=chat.id,
        name=chat.customer_name,
        channel=chat.channel.value,
        online=chat.online,
        unread=chat.unread_count,
        mode=chat.mode.value,
        profile=profile,
        messages=formatted_messages,
        group_id=chat.group_id,
        group_name=chat.group_name
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
    from app.models.ticket import Ticket, TicketStatus

    chat = db.query(Chat).filter(Chat.id == chat_id).first()

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found"
        )

    if data.mode is not None:
        chat.mode = ChatMode[data.mode.value]

        # CRITICAL: When closing chat, KEEP chat but mark as closed + resolve ticket
        # This preserves ticket stats. When customer messages again, chat will be reset.
        if data.mode.value == "closed":
            # Mark ticket as RESOLVED (keep for statistics!)
            ticket = db.query(Ticket).filter(Ticket.chat_id == chat_id).first()
            if ticket:
                ticket.status = TicketStatus.resolved
                ticket.resolved_at = datetime.now()
                # Preserve which agent handled this chat before unassigning
                if not ticket.assigned_agent_id and chat.assigned_agent_id:
                    ticket.assigned_agent_id = chat.assigned_agent_id

            # Unassign agent so chat doesn't show in agent's list
            chat.assigned_agent_id = None
            chat.mode = ChatMode.closed

            # Delete all messages for fresh start
            db.query(Message).filter(Message.chat_id == chat_id).delete()

            db.commit()

            # Return response indicating chat is closed
            return ChatResponse(
                id=chat.id,
                name=chat.customer_name,
                channel=chat.channel.value,
                online=False,
                unread=0,
                mode="closed",
                profile=CustomerProfile(phone=chat.customer_phone),
                messages=[],
                group_id=chat.group_id,
                group_name=chat.group_name
            )

    if data.assigned_agent_id is not None:
        chat.assigned_agent_id = data.assigned_agent_id
        # Also update the ticket so agent performance is tracked
        from app.models.ticket import Ticket, TicketStatus
        ticket = db.query(Ticket).filter(Ticket.chat_id == chat_id).first()
        if ticket and ticket.status not in [TicketStatus.resolved, TicketStatus.closed]:
            ticket.assigned_agent_id = data.assigned_agent_id
            if ticket.status.value == "pending":
                ticket.status = TicketStatus.assigned
                ticket.assigned_at = datetime.now()

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

    # Tambahkan tanda tangan agent otomatis ke setiap pesan agent
    if data.sender == "agent" and data.agent_id:
        from app.models.agent_profile import AgentProfile
        from app.models.user import User as UserModel
        agent_profile = db.query(AgentProfile).filter(AgentProfile.user_id == data.agent_id).first()
        if agent_profile and agent_profile.display_name:
            agent_display = agent_profile.display_name
        else:
            agent_user = db.query(UserModel).filter(UserModel.id == data.agent_id).first()
            agent_display = agent_user.name if agent_user else f"Agent {data.agent_id}"
        data.text = f"{data.text}\n~ {agent_display}"

    message = Message(
        chat_id=data.chat_id,
        text=data.text,
        sender=MessageSender[data.sender.value],
        status=MessageStatus.sent,
        agent_id=data.agent_id if data.sender == "agent" else None,
        media_url=data.media_url,
        media_type=data.media_type,
        media_filename=data.media_filename,
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
    if data.sender == "agent" and chat.channel.value == "whatsapp":
        try:
            # For GROUP chats: use group_id (e.g., 120363423035678646@g.us)
            # For PRIVATE chats: use customer_phone with @c.us suffix
            mentions = None
            message_text = data.text

            if chat.group_id:
                target = chat.group_id  # Already in format: 120363423035678646@g.us
                # Auto-mention the last participant who sent a message
                if chat.last_participant_jid:
                    mentions = [chat.last_participant_jid]
                    # Get the last customer message to get participant name
                    last_customer_msg = db.query(Message).filter(
                        Message.chat_id == chat.id,
                        Message.sender == MessageSender.customer,
                        Message.participant_name != None
                    ).order_by(Message.created_at.desc()).first()

                    if last_customer_msg and last_customer_msg.participant_name:
                        # Format: "@Name message" - the @mention will be linked to the JID
                        message_text = f"@{last_customer_msg.participant_name} {data.text}"
                        logger.info(f"Sending to GROUP: {target} mentioning: {last_customer_msg.participant_name}")
                    else:
                        logger.info(f"Sending to GROUP: {target} with mention (no name)")
                else:
                    logger.info(f"Sending to GROUP: {target} (no mention)")
            else:
                target = f"{chat.customer_phone}@c.us"
                logger.info(f"Sending to PRIVATE: {target}")

            # Send media or text via WhatsApp
            if data.media_url and data.media_type:
                from app.whapi.client import send_media
                result = send_media(
                    to=target,
                    media_url=data.media_url,
                    media_type=data.media_type,
                    caption=message_text if message_text else None,
                    filename=data.media_filename,
                    mentions=mentions,
                )
            else:
                result = send_text(target, message_text, mentions)

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
        agent_id=message.agent_id,
        media_url=message.media_url,
        media_type=message.media_type,
        media_filename=message.media_filename,
        participant_phone=message.participant_phone,
        participant_name=message.participant_name
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

def update_tag_chat_agent(message_id: int, new_agent_name: str, db: Session):
    """Update the ~ Agent Name tag at the end of an agent message."""
    message = db.query(Message).filter(Message.id == message_id).first()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )

    if message.sender != MessageSender.agent:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only edit agent messages"
        )

    # Replace existing ~ Tag or append new one
    import re
    new_tag = f"~ {new_agent_name.strip()}"
    if re.search(r"\n~ .+$", message.text):
        # Ganti tag yang sudah ada
        message.text = re.sub(r"\n~ .+$", f"\n{new_tag}", message.text)
    else:
        # Tambahkan tag baru di akhir
        message.text = f"{message.text}\n{new_tag}"

    db.commit()
    db.refresh(message)

    return MessageResponse(
        id=message.id,
        text=message.text,
        sender=message.sender.value,
        status=message.status.value,
        time=message.created_at.strftime("%H:%M"),
        agent_id=message.agent_id,
        media_url=message.media_url,
        media_type=message.media_type,
        media_filename=message.media_filename,
        participant_phone=message.participant_phone,
        participant_name=message.participant_name
    )


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
        agent_id=message.agent_id,
        media_url=message.media_url,
        media_type=message.media_type,
        media_filename=message.media_filename,
        participant_phone=message.participant_phone,
        participant_name=message.participant_name
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
