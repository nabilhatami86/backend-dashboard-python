from fastapi import APIRouter, Request, BackgroundTasks, HTTPException, Depends
from sqlalchemy.orm import Session
import logging
from app.whapi.client import send_text
from app.services.bot_service import handle_bot
from app.services.queue_service import QueueService
from app.config.deps import get_db
from app.models.chat import Chat, ChatMode, ChatChannel
from app.models.message import Message, MessageSender, MessageStatus
from app.models.ticket import TicketPriority
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()


def get_or_create_chat(db: Session, phone: str, name: str = None) -> Chat:
    """Get existing chat or create new one from WhatsApp message"""
    # Try to find existing chat by phone
    chat = db.query(Chat).filter(Chat.customer_phone == phone).first()

    if chat:
        # Update online status and last message time
        chat.online = True
        chat.last_message_at = datetime.now()

        # Update name if provided and more descriptive than current name
        if name:
            # Update if current name is phone number, generic name, LID format, or test name
            should_update = (
                not chat.customer_name or
                "@c.us" in chat.customer_name or
                "@g.us" in chat.customer_name or
                "@lid" in chat.customer_name or  # LID format
                chat.customer_name.startswith("628") or
                "Test" in chat.customer_name
            )
            if should_update and name != chat.customer_name:
                old_name = chat.customer_name
                chat.customer_name = name
                logger.info(f"Updated chat {chat.id} name from '{old_name}' to '{name}'")

        db.commit()
        db.refresh(chat)
        return chat

    # Create new chat
    # For LID format, prefer pushName as display name
    if not name:
        if "@lid" in phone:
            # LID format - use a placeholder, will be updated when pushName is received
            name = f"Customer ({phone.split('@')[0][:8]}...)"
        else:
            name = phone.replace("@c.us", "").replace("@g.us", "")

    new_chat = Chat(
        customer_name=name,
        customer_phone=phone,
        customer_email=None,
        customer_address=None,
        channel=ChatChannel.whatsapp,
        mode=ChatMode.bot,  # Start in bot mode
        online=True,
        unread_count=0,
        last_message_at=datetime.now(),
    )

    db.add(new_chat)
    db.commit()
    db.refresh(new_chat)

    logger.info(f"Created new chat for {phone} with name: {name}")
    return new_chat


def save_customer_message(db: Session, chat: Chat, text: str) -> Message:
    """Save customer message to database"""
    message = Message(
        chat_id=chat.id,
        text=text,
        sender=MessageSender.customer,
        status=MessageStatus.sent,
        created_at=datetime.now(),
    )

    db.add(message)

    # Increment unread count
    chat.unread_count += 1
    chat.last_message_at = datetime.now()

    db.commit()
    db.refresh(message)

    logger.info(f"Saved customer message to chat {chat.id}")
    return message


def save_bot_reply(db: Session, chat: Chat, text: str) -> Message:
    """Save bot reply to database"""
    message = Message(
        chat_id=chat.id,
        text=text,
        sender=MessageSender.agent,
        status=MessageStatus.sent,
        created_at=datetime.now(),
        agent_id=None,  # Bot messages have no agent_id
    )

    db.add(message)
    chat.last_message_at = datetime.now()
    db.commit()
    db.refresh(message)

    logger.info(f"Saved bot reply to chat {chat.id}")
    return message


def ensure_ticket_exists(db: Session, chat: Chat) -> None:
    """
    Ensure ticket exists for agent mode chats
    Auto-create and assign if needed
    """
    from app.models.ticket import Ticket

    # Check if ticket already exists
    existing_ticket = db.query(Ticket).filter(Ticket.chat_id == chat.id).first()
    if existing_ticket:
        logger.info(f"Ticket already exists for chat {chat.id}: ticket_id={existing_ticket.id}")
        return

    # Create ticket and auto-assign
    queue_service = QueueService(db)

    # Determine priority based on keywords (simple logic)
    priority = TicketPriority.medium
    # You can add more sophisticated priority detection here

    ticket = queue_service.create_ticket_for_chat(
        chat_id=chat.id,
        priority=priority,
        auto_assign=True  # Auto-assign to available agent
    )

    logger.info(f"Created ticket {ticket.id} for chat {chat.id} with priority {priority.value}")

    if ticket.assigned_agent_id:
        logger.info(f"Auto-assigned ticket {ticket.id} to agent {ticket.assigned_agent_id}")
    else:
        logger.warning(f"No available agent for ticket {ticket.id}, staying in queue")


@router.post("/webhook/whapi")
@router.post("/webhook/whapi/messages")  # WHAPI sends to /messages endpoint
@router.post("/webhook/baileys")  # Baileys service sends to this endpoint
async def whapi_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    try:
        data = await request.json()
        logger.info(f"Received webhook data: {data}")
    except Exception as e:
        logger.error(f"Failed to parse webhook JSON: {e}")
        raise HTTPException(status_code=400, detail="invalid json")

    msgs = data.get("messages")
    if not msgs or not isinstance(msgs, list):
        return {"status": "ignored", "reason": "no messages"}

    msg = msgs[0]
    sender = msg.get("from") or msg.get("sender")

    # Get sender name if available
    sender_name = None
    if msg.get("from_name"):
        sender_name = msg["from_name"]
    elif msg.get("pushname"):
        sender_name = msg["pushname"]

    # Extract text
    text = None
    if isinstance(msg.get("text"), dict):
        text = msg["text"].get("body")
    else:
        text = msg.get("body") or msg.get("message") or msg.get("text")

    if not sender or not text:
        logger.info("webhook ignored: missing sender or text")
        return {"status": "ignored", "reason": "missing sender or text"}

    # Get or create chat in database
    chat = get_or_create_chat(db, sender, sender_name)

    # Save customer message to database
    save_customer_message(db, chat, text)

    # Check if customer is requesting agent (keyword: "agent")
    text_lower = text.strip().lower()
    if text_lower == "agent" and chat.mode == ChatMode.bot:
        # Switch to agent mode
        chat.mode = ChatMode.agent
        db.commit()
        db.refresh(chat)
        logger.info(f"Chat {chat.id} switched to agent mode by customer request")

        # Create ticket for agent pickup
        ensure_ticket_exists(db, chat)

        # Send confirmation to customer
        confirmation = "Baik, Anda akan terhubung dengan agent kami. Mohon tunggu sebentar."
        save_bot_reply(db, chat, confirmation)
        background_tasks.add_task(send_text, sender, confirmation)

        return {
            "status": "ok",
            "mode": "agent",
            "chat_id": chat.id,
            "message": "Switched to agent mode, ticket created"
        }

    # Check chat mode from database
    if chat.mode == ChatMode.agent:
        # In agent mode - ensure ticket exists and is assigned
        ensure_ticket_exists(db, chat)
        logger.info(f"Chat {chat.id} is in agent mode, skipping bot reply")

        # If customer typed "agent" again, send confirmation
        if text_lower == "agent":
            confirmation = "Anda sudah terhubung ke agent. Mohon tunggu balasan."
            save_bot_reply(db, chat, confirmation)
            background_tasks.add_task(send_text, sender, confirmation)

        return {"status": "ok", "mode": "agent", "chat_id": chat.id}

    if chat.mode == ChatMode.paused:
        # In paused mode - don't send bot reply
        logger.info(f"Chat {chat.id} is paused, skipping bot reply")
        return {"status": "ok", "mode": "paused", "chat_id": chat.id}

    if chat.mode == ChatMode.closed:
        # Closed chat - customer is starting a new conversation
        # Reset chat to bot mode so it re-enters the ticket queue
        logger.info(f"Chat {chat.id} was closed, resetting to bot mode for new conversation")
        chat.mode = ChatMode.bot
        # Note: assigned_agent_id is already NULL from when it was closed
        db.commit()
        db.refresh(chat)
        # Continue to bot reply below (fall through to bot mode handling)

    # Bot mode - generate and send reply
    try:
        reply = handle_bot(sender, text)
    except Exception as e:
        logger.exception("bot handler failed")
        return {"status": "error", "error": str(e)}

    if reply:
        # Save bot reply to database
        save_bot_reply(db, chat, reply)

        # Send to WhatsApp in background
        background_tasks.add_task(send_text, sender, reply)

        return {
            "status": "ok",
            "mode": "bot",
            "chat_id": chat.id,
            "bot_replied": True
        }

    return {
        "status": "ok",
        "mode": "bot",
        "chat_id": chat.id,
        "bot_replied": False
    }
