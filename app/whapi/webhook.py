from fastapi import APIRouter, Request, BackgroundTasks, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import asyncio
import logging
import base64
import os
import uuid
from datetime import datetime
import time
from threading import Lock

from app.whapi.client import send_text, send_presence
from app.services.bot_service import handle_bot
from app.services.queue_service import QueueService
from app.services.ws_manager import manager as ws_manager
from app.config.deps import get_db
from app.models.chat import Chat, ChatMode, ChatChannel
from app.models.message import Message, MessageSender, MessageStatus
from app.models.ticket import Ticket, TicketStatus, TicketPriority

logger = logging.getLogger(__name__)
router = APIRouter()

# Pesan yang dikirim ke customer saat eskalasi ke CS
ESCALATION_REPLY = "Baik kak, akan kami hubungi ke Customer Service kita, Sebentar ya"

_ESCALATION_TRIGGERS = [
    "silahkan hubungi kami melalui whatsapp",
    "hubungi kami melalui whatsapp",
    "please contact us via whatsapp",
    "silakan hubungi kami",
    "bantu saya untuk menjawab pertanyaan ini",
    "baik kak, akan kami hubungi ke customer service kita, sebentar ya"
]


def _is_escalation_reply(reply: str) -> bool:
    normalized = reply.lower().strip()
    return any(trigger in normalized for trigger in _ESCALATION_TRIGGERS)


class MessageDedupCache:
    def __init__(self, max_size=1000, ttl_seconds=10):
        self.cache = {}
        self.lock = Lock()
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds

    def is_duplicate(self, phone: str, text: str, msg_timestamp=None) -> bool:
        # timestamp dari Baileys bisa berupa dict protobuf: {"low": ..., "high": ..., "unsigned": true}
        if isinstance(msg_timestamp, dict):
            msg_timestamp = msg_timestamp.get('low') or int(time.time())
        rounded_ts = int(msg_timestamp) if msg_timestamp else int(time.time())
        message_key = f"{phone}:{text}:{rounded_ts}"

        with self.lock:
            now = time.time()
            expired_keys = [k for k, v in self.cache.items() if now - v > self.ttl_seconds]
            for k in expired_keys:
                del self.cache[k]

            if message_key in self.cache:
                logger.warning(f"[DEDUP] Duplicate message: {message_key}")
                return True

            self.cache[message_key] = now
            if len(self.cache) > self.max_size:
                oldest_key = min(self.cache.items(), key=lambda x: x[1])[0]
                del self.cache[oldest_key]

            return False


message_dedup_cache = MessageDedupCache()


class ChatProcessingLock:
    def __init__(self):
        self.locks = {}
        self.master_lock = Lock()

    def get_lock(self, chat_id: int):
        with self.master_lock:
            if chat_id not in self.locks:
                self.locks[chat_id] = Lock()
            return self.locks[chat_id]

    def cleanup_old_locks(self):
        with self.master_lock:
            if len(self.locks) > 100:
                keys_to_remove = list(self.locks.keys())[:50]
                for key in keys_to_remove:
                    del self.locks[key]


chat_processing_lock = ChatProcessingLock()


def normalize_phone(sender: str) -> str:
    return sender.split("@")[0]


def get_or_create_chat(db: Session, phone: str, name: str = None, group_id: str = None, group_name: str = None, participant_jid: str = None, participant_phone: str = None, participant_name: str = None) -> Chat:
    if group_id:
        chat = db.query(Chat).filter(
            Chat.group_id == group_id,
            Chat.customer_phone == participant_phone
        ).with_for_update().first()

        if chat:
            chat.online = True
            chat.last_message_at = datetime.now()
            if group_name:
                chat.group_name = group_name
            if participant_name and chat.customer_name != participant_name:
                chat.customer_name = participant_name
            if participant_jid:
                chat.last_participant_jid = participant_jid
            db.commit()
            db.refresh(chat)
            return chat

        new_chat = Chat(
            customer_name=participant_name or participant_phone or "Anggota Grup",
            customer_phone=participant_phone,
            channel=ChatChannel.whatsapp,
            mode=ChatMode.bot,
            online=True,
            unread_count=0,
            last_message_at=datetime.now(),
            group_id=group_id,
            group_name=group_name,
            last_participant_jid=participant_jid,
        )
    else:
        chat = db.query(Chat).filter(
            Chat.customer_phone == phone,
            Chat.group_id.is_(None)
        ).with_for_update().first()

        if chat:
            chat.online = True
            chat.last_message_at = datetime.now()
            if name and chat.customer_name != name:
                chat.customer_name = name
            db.commit()
            db.refresh(chat)
            return chat

        new_chat = Chat(
            customer_name=name or phone,
            customer_phone=phone,
            channel=ChatChannel.whatsapp,
            mode=ChatMode.bot,
            online=True,
            unread_count=0,
            last_message_at=datetime.now(),
            group_id=None,
            group_name=None,
        )

    db.add(new_chat)
    try:
        db.commit()
    except IntegrityError:
        # Race condition: chat baru saja dibuat oleh request lain
        db.rollback()
        if group_id:
            chat = db.query(Chat).filter(Chat.group_id == group_id).with_for_update().first()
        else:
            chat = db.query(Chat).filter(
                Chat.customer_phone == phone,
                Chat.group_id.is_(None)
            ).with_for_update().first()
        return chat

    db.refresh(new_chat)
    return new_chat


UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

MIMETYPE_TO_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
    "audio/ogg": ".ogg",
    "audio/mpeg": ".mp3",
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}


def save_incoming_media(media_base64: str, media_type: str, mimetype: str, filename: str = None) -> str | None:
    """Decode base64 media dari WhatsApp dan simpan ke folder uploads/. Return relative URL."""
    try:
        data = base64.b64decode(media_base64)
        ext = MIMETYPE_TO_EXT.get(mimetype, "")
        if not ext and filename:
            ext = os.path.splitext(filename)[1] or ""
        if not ext:
            ext = ".bin"
        unique_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_name)
        with open(file_path, "wb") as f:
            f.write(data)
        logger.info(f"[MEDIA SAVED] {unique_name} ({len(data)} bytes)")
        return f"/uploads/{unique_name}"
    except Exception as e:
        logger.error(f"[MEDIA SAVE ERROR] {e}")
        return None


def save_customer_message(
    db: Session,
    chat: Chat,
    text: str,
    participant_phone: str = None,
    participant_name: str = None,
    media_url: str = None,
    media_type: str = None,
    media_filename: str = None,
) -> Message:
    message = Message(
        chat_id=chat.id,
        text=text,
        sender=MessageSender.customer,
        status=MessageStatus.sent,
        created_at=datetime.now(),
        participant_phone=participant_phone,
        participant_name=participant_name,
        media_url=media_url,
        media_type=media_type,
        media_filename=media_filename,
    )
    db.add(message)
    chat.unread_count += 1
    chat.last_message_at = datetime.now()
    db.commit()
    db.refresh(message)
    return message


def save_bot_reply(db: Session, chat: Chat, text: str) -> Message:
    message = Message(
        chat_id=chat.id,
        text=text,
        sender=MessageSender.agent,
        status=MessageStatus.sent,
        created_at=datetime.now(),
        agent_id=None,
    )
    db.add(message)
    chat.last_message_at = datetime.now()
    db.commit()
    db.refresh(message)
    return message


def get_or_create_ticket(db: Session, chat: Chat, priority: TicketPriority = TicketPriority.medium) -> Ticket:
    ticket = db.query(Ticket).filter(Ticket.chat_id == chat.id).first()

    if ticket:
        if ticket.status not in [TicketStatus.resolved, TicketStatus.closed]:
            return ticket

        # Ticket sudah resolved/closed → reopen untuk percakapan baru
        # Constraint 1 chat = 1 ticket, jadi kita reset yang ada
        logger.info(f"[TICKET REOPEN] ticket_id={ticket.id} old_status={ticket.status.value}")

        ticket.status = TicketStatus.pending
        ticket.priority = priority
        ticket.assigned_agent_id = None
        ticket.created_at = datetime.now()
        ticket.assigned_at = None
        ticket.first_response_at = None
        ticket.resolved_at = None
        ticket.notes = None
        ticket.tags = None

        chat.assigned_agent_id = None

        db.commit()
        db.refresh(ticket)

        logger.info(f"[TICKET REOPENED] ticket_id={ticket.id} chat_id={chat.id} priority={priority.value}")
        return ticket

    new_ticket = Ticket(
        chat_id=chat.id,
        status=TicketStatus.pending,
        priority=priority,
        created_at=datetime.now(),
    )

    db.add(new_ticket)
    try:
        db.commit()
    except IntegrityError:
        # Race condition: ticket sudah dibuat oleh request lain
        db.rollback()
        return db.query(Ticket).filter(Ticket.chat_id == chat.id).first()

    db.refresh(new_ticket)
    logger.info(f"[TICKET CREATED] ticket_id={new_ticket.id} chat_id={chat.id} priority={priority.value}")
    return new_ticket


@router.post("/webhook/baileys")
async def whapi_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        data = await request.json()
    except Exception as e:
        logger.error(f"[WEBHOOK] Failed to parse JSON: {e}")
        raise HTTPException(status_code=400, detail="invalid json")

    # Deteksi format: single message (Baileys) vs array messages (WHAPI)
    if "from" in data and "text" in data:
        msgs = [data]
    elif "messages" in data:
        msgs = data.get("messages")
    else:
        logger.error(f"[WEBHOOK] Unknown format: {list(data.keys())}")
        return {"status": "ignored"}

    if not msgs:
        return {"status": "ignored"}

    for msg in msgs:
        try:
            sender_raw = msg.get("from")
            if not sender_raw:
                continue

            is_group = sender_raw.endswith("@g.us")

            is_mentioned = msg.get("isMentioned", False)
            if not is_mentioned and msg.get("mentionedJid"):
                is_mentioned = len(msg.get("mentionedJid", [])) > 0

            if not is_mentioned:
                text_body = msg.get("text", {}).get("body") if isinstance(msg.get("text"), dict) else msg.get("text")
                if text_body and "@" in text_body and is_group:
                    is_mentioned = True

            # Pesan grup tanpa mention → abaikan
            if is_group and not is_mentioned:
                logger.info(f"[WEBHOOK SKIP] Group message tanpa mention dari {sender_raw}")
                continue

            participant_phone = None
            participant_name = None
            participant_jid = None

            if is_group:
                participant_jid = msg.get("participant")
                if not participant_jid:
                    logger.warning(f"[WEBHOOK] Group message tanpa participant JID, skip")
                    continue
                participant_phone = normalize_phone(participant_jid)
                participant_name = msg.get("participantName") or msg.get("pushname") or msg.get("pushName") or participant_phone
                phone = None
            else:
                phone = normalize_phone(sender_raw)

            sender_name = msg.get("pushname") or msg.get("pushName") or (phone or participant_phone)

            text = (
                msg.get("text", {}).get("body")
                if isinstance(msg.get("text"), dict)
                else msg.get("text")
            )

            has_media = bool(msg.get("mediaBase64") and msg.get("mediaType"))
            media_type_label = msg.get("mediaType", "").capitalize() if has_media else ""

            if not text and not has_media:
                continue

            if not text and has_media:
                text = f"[{media_type_label or 'Media'}]"

            text = text.strip()

            # Cek duplikat untuk menghindari race condition double-processing
            msg_timestamp = msg.get("timestamp") or msg.get("messageTimestamp")
            dedup_key = f"{sender_raw}:{participant_phone}" if is_group else phone
            if message_dedup_cache.is_duplicate(dedup_key, text, msg_timestamp):
                logger.warning(f"[WEBHOOK SKIP DUPLICATE] key={dedup_key} text='{text[:30]}'")
                continue

            # Hapus mention tag dari teks sebelum diproses bot
            # contoh: "@6281234567890 halo bot" → "halo bot"
            if is_group and text.startswith("@"):
                space_idx = text.find(" ")
                if space_idx != -1:
                    text = text[space_idx:].strip()

            group_id = sender_raw if is_group else None
            group_name = msg.get("groupName") if is_group else None

            chat = get_or_create_chat(
                db, phone, sender_name,
                group_id=group_id,
                group_name=group_name,
                participant_jid=participant_jid,
                participant_phone=participant_phone,
                participant_name=participant_name
            )

            incoming_media_url = None
            incoming_media_type = None
            incoming_media_filename = None

            media_base64 = msg.get("mediaBase64")
            media_type_raw = msg.get("mediaType")
            media_filename_raw = msg.get("mediaFilename")
            media_mimetype = msg.get("mediaMimetype")

            if media_base64 and media_type_raw:
                incoming_media_url = save_incoming_media(
                    media_base64, media_type_raw, media_mimetype or "", media_filename_raw
                )
                if incoming_media_url:
                    incoming_media_type = media_type_raw
                    incoming_media_filename = media_filename_raw

            save_customer_message(
                db, chat, text,
                participant_phone=participant_phone,
                participant_name=participant_name,
                media_url=incoming_media_url,
                media_type=incoming_media_type,
                media_filename=incoming_media_filename,
            )

            await ws_manager.broadcast(chat.id, {"type": "new_message", "chat_id": chat.id})

            # Kirim "sedang mengetik..." ke WA customer — fire-and-forget, tidak block apapun
            wa_target = sender_raw if is_group else f"{phone}@c.us"
            background_tasks.add_task(send_presence, wa_target, "composing")

            reply = None
            # Lock per-chat: mencegah concurrent processing pesan dari chat yang sama
            chat_lock = chat_processing_lock.get_lock(chat.id)

            with chat_lock:
                db.refresh(chat)

                # Auto-reset ke bot jika:
                # - closed: customer mulai chat baru
                # - paused: customer kirim pesan tapi belum ada agent yang assign
                needs_reset = chat.mode == ChatMode.closed or (
                    chat.mode == ChatMode.paused and not chat.assigned_agent_id
                )
                if needs_reset:
                    logger.info(f"[BOT RESET] chat_id={chat.id} {chat.mode.value} → bot")
                    chat.mode = ChatMode.bot
                    chat.assigned_agent_id = None
                    existing_ticket = db.query(Ticket).filter(Ticket.chat_id == chat.id).first()
                    if existing_ticket and existing_ticket.status in [TicketStatus.resolved, TicketStatus.closed]:
                        existing_ticket.status = TicketStatus.pending
                        existing_ticket.assigned_agent_id = None
                        existing_ticket.created_at = datetime.now()
                        existing_ticket.assigned_at = None
                        existing_ticket.first_response_at = None
                        existing_ticket.resolved_at = None
                        logger.info(f"[BOT RESET] ticket_id={existing_ticket.id} reopened")
                    db.commit()
                    db.refresh(chat)

                # Customer ketik "#human" → langsung eskalasi tanpa nunggu bot
                text_lower = text.strip().lower()
                is_human_trigger = text_lower in ("human", "#human") or "#human" in text_lower
                if is_human_trigger and chat.mode == ChatMode.bot:
                    logger.info(f"[HUMAN TRIGGER] chat_id={chat.id} → escalating")
                    await ws_manager.broadcast(chat.id, {"type": "typing", "sender": "bot", "is_typing": True})
                    try:
                        get_or_create_ticket(db, chat, priority=TicketPriority.medium)
                    except Exception as e:
                        logger.exception(f"[HUMAN TRIGGER] Failed to create ticket: {e}")
                    chat.mode = ChatMode.paused
                    db.commit()

                    sender_jid = msg.get("participant")
                    target = sender_raw if is_group else f"{phone}@c.us"
                    if is_group:
                        mention_phone = participant_phone or "User"
                        escalation_text = f"@{mention_phone} {ESCALATION_REPLY}"
                        mentions = [sender_jid] if sender_jid else None
                    else:
                        escalation_text = ESCALATION_REPLY
                        mentions = None

                    try:
                        save_bot_reply(db, chat, escalation_text)
                    except Exception as e:
                        logger.exception(f"[HUMAN TRIGGER] Failed to save escalation reply: {e}")

                    await asyncio.to_thread(send_presence, target, "paused")
                    await ws_manager.broadcast(chat.id, {"type": "typing", "sender": "bot", "is_typing": False})
                    await ws_manager.broadcast(chat.id, {"type": "new_message", "chat_id": chat.id})
                    background_tasks.add_task(send_text, target, escalation_text, mentions)
                    continue

                # Bot hanya balas saat mode=bot; mode=agent/paused → diam
                should_bot_reply = chat.mode == ChatMode.bot
                if not should_bot_reply:
                    logger.warning(f"[BOT SKIP] chat_id={chat.id} mode={chat.mode.value}")
                    background_tasks.add_task(send_presence, wa_target, "paused")
                    continue

                bot_user_identifier = sender_raw if is_group else phone

            # Lock dilepas — typing broadcast dan AI call di luar lock supaya event loop
            # bisa flush WebSocket frame "typing: true" ke browser sebelum HTTP call ke AI mulai
            await ws_manager.broadcast(chat.id, {"type": "typing", "sender": "bot", "is_typing": True})
            try:
                reply = await asyncio.to_thread(handle_bot, bot_user_identifier, text)
            except Exception as e:
                logger.exception(f"[BOT ERROR] handle_bot failed: {e}")
                await asyncio.to_thread(send_presence, wa_target, "paused")
                await ws_manager.broadcast(chat.id, {"type": "typing", "sender": "bot", "is_typing": False})
                continue
            await asyncio.to_thread(send_presence, wa_target, "paused")
            await ws_manager.broadcast(chat.id, {"type": "typing", "sender": "bot", "is_typing": False})

            if reply:
                # Jika bot escalate → buat ticket dan set paused
                if _is_escalation_reply(reply):
                    reply = ESCALATION_REPLY
                    logger.info(f"[ESCALATION] chat_id={chat.id} is_group={is_group}")
                    try:
                        ticket = get_or_create_ticket(db, chat, priority=TicketPriority.medium)
                        logger.info(f"[ESCALATION] ticket_id={ticket.id} status={ticket.status}")
                    except Exception as e:
                        logger.exception(f"[ESCALATION ERROR] Failed to create ticket: {e}")
                    # Set paused SETELAH get_or_create_ticket agar tidak di-override
                    chat.mode = ChatMode.paused
                    db.commit()

                sender_jid = msg.get("participant")

                if is_group:
                    # Pakai nomor HP untuk mention WA (@nomorhp), bukan nama display
                    mention_phone = participant_phone or "User"
                    reply_text = f"@{mention_phone} {reply}"
                    mentions = [sender_jid] if sender_jid else None
                else:
                    reply_text = reply
                    sender_jid = None
                    mentions = None

                try:
                    save_bot_reply(db, chat, reply_text)
                except Exception as e:
                    logger.exception(f"Failed to save bot reply: {e}")

                await ws_manager.broadcast(chat.id, {"type": "new_message", "chat_id": chat.id})

                target = sender_raw if is_group else f"{phone}@c.us"
                try:
                    background_tasks.add_task(send_text, target, reply_text, mentions)
                except Exception as e:
                    logger.exception(f"Failed to queue send task: {e}")
            else:
                # AI tidak bisa jawab → eskalasi ke CS
                logger.info(f"[BOT NO REPLY] chat_id={chat.id} → escalating")
                try:
                    ticket = get_or_create_ticket(db, chat, priority=TicketPriority.medium)
                    logger.info(f"[ESCALATION] ticket_id={ticket.id} → paused")
                except Exception as e:
                    logger.exception(f"[ESCALATION ERROR] {e}")
                # Set paused SETELAH get_or_create_ticket agar tidak di-override
                chat.mode = ChatMode.paused
                db.commit()

                target = sender_raw if is_group else f"{phone}@c.us"
                sender_jid = msg.get("participant")
                if is_group:
                    mention_phone = participant_phone or "User"
                    escalation_text = f"@{mention_phone} {ESCALATION_REPLY}"
                    mentions = [sender_jid] if sender_jid else None
                else:
                    escalation_text = ESCALATION_REPLY
                    mentions = None

                try:
                    save_bot_reply(db, chat, escalation_text)
                    background_tasks.add_task(send_text, target, escalation_text, mentions)
                    await ws_manager.broadcast(chat.id, {"type": "new_message", "chat_id": chat.id})
                    logger.info(f"[ESCALATION SENT] target={target}")
                except Exception as e:
                    logger.exception(f"[ESCALATION SEND ERROR] {e}")
        except Exception as e:
            logger.exception(f"[WEBHOOK ERROR] Unexpected error: {e}")

    return {"status": "ok"}


@router.post("/webhook/typing")
async def typing_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Terima typing presence dari Baileys dan broadcast ke dashboard via WebSocket.
    Payload: {"from": "628xxx@c.us", "is_typing": true, "is_group": false}
    """
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json")

    sender_raw = data.get("from")
    is_typing = bool(data.get("is_typing", False))
    is_group = bool(data.get("is_group", False))
    participant_raw = data.get("participant")

    if not sender_raw:
        return {"status": "ignored"}

    phone = sender_raw.split("@")[0]
    if is_group:
        if not participant_raw:
            logger.warning(f"[TYPING] Group typing tanpa participant, skip. group={sender_raw}")
            return {"status": "ignored"}
        participant_phone = participant_raw.split("@")[0]
        chat = db.query(Chat).filter(
            Chat.group_id == sender_raw,
            Chat.customer_phone == participant_phone
        ).first()
    else:
        chat = db.query(Chat).filter(
            Chat.customer_phone == phone,
            Chat.group_id.is_(None)
        ).first()

    if not chat:
        logger.warning(f"[TYPING] chat_not_found phone={phone} is_group={is_group}")
        return {"status": "chat_not_found"}

    await ws_manager.broadcast(chat.id, {
        "type": "typing",
        "sender": "customer",
        "is_typing": is_typing,
    })

    return {"status": "ok"}
