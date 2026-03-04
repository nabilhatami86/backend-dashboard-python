from fastapi import APIRouter, Request, BackgroundTasks, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import logging
import base64
import os
import uuid
from datetime import datetime
import time
from threading import Lock

from app.whapi.client import send_text
from app.services.bot_service import handle_bot
from app.services.queue_service import QueueService
from app.config.deps import get_db
from app.models.chat import Chat, ChatMode, ChatChannel
from app.models.message import Message, MessageSender, MessageStatus
from app.models.ticket import Ticket, TicketStatus, TicketPriority

logger = logging.getLogger(__name__)
router = APIRouter()

# =========================
# MESSAGE DEDUPLICATION CACHE
# =========================
# Cache untuk prevent duplicate message processing (race condition)
# Format: {message_key: timestamp}
# message_key = f"{phone}:{text}:{timestamp_rounded}"
# Simpan max 1000 message dalam 10 detik terakhir
class MessageDedupCache:
    def __init__(self, max_size=1000, ttl_seconds=10):
        self.cache = {}  # {message_key: insert_time}
        self.lock = Lock()
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds

    def is_duplicate(self, phone: str, text: str, msg_timestamp: int = None) -> bool:
        """
        Check apakah message ini duplicate (baru diproses dalam TTL window).
        Return True jika duplicate (harus di-skip), False jika baru.
        """
        # Round timestamp ke nearest second untuk group messages yang datang bersamaan
        rounded_ts = msg_timestamp // 1 if msg_timestamp else int(time.time())
        message_key = f"{phone}:{text}:{rounded_ts}"

        with self.lock:
            now = time.time()

            # Cleanup old entries (older than TTL)
            expired_keys = [k for k, v in self.cache.items() if now - v > self.ttl_seconds]
            for k in expired_keys:
                del self.cache[k]

            # Check if this message was recently processed
            if message_key in self.cache:
                logger.warning(f"[DEDUP] Duplicate message detected: {message_key}")
                return True  # Duplicate!

            # Add to cache
            self.cache[message_key] = now

            # Limit cache size (remove oldest if too big)
            if len(self.cache) > self.max_size:
                oldest_key = min(self.cache.items(), key=lambda x: x[1])[0]
                del self.cache[oldest_key]

            return False  # Not duplicate

# Global dedup cache instance
message_dedup_cache = MessageDedupCache()

# =========================
# PER-CHAT PROCESSING LOCK
# =========================
# Lock untuk prevent concurrent bot processing pada chat yang sama
# Jika chat sedang diproses, request lain harus tunggu
class ChatProcessingLock:
    def __init__(self):
        self.locks = {}  # {chat_id: Lock}
        self.master_lock = Lock()

    def get_lock(self, chat_id: int):
        """Get or create lock for specific chat"""
        with self.master_lock:
            if chat_id not in self.locks:
                self.locks[chat_id] = Lock()
            return self.locks[chat_id]

    def cleanup_old_locks(self):
        """Cleanup locks yang tidak digunakan (optional, untuk prevent memory leak)"""
        with self.master_lock:
            # Keep only 100 most recent locks
            if len(self.locks) > 100:
                # Remove oldest 50 locks
                keys_to_remove = list(self.locks.keys())[:50]
                for key in keys_to_remove:
                    del self.locks[key]

# Global chat processing lock instance
chat_processing_lock = ChatProcessingLock()


# =========================
# helper
# =========================
def normalize_phone(sender: str) -> str:
    return sender.split("@")[0]


# =========================
# CHAT
# =========================
def get_or_create_chat(db: Session, phone: str, name: str = None, group_id: str = None, group_name: str = None, participant_jid: str = None, participant_phone: str = None, participant_name: str = None) -> Chat:
    """
    Get or create chat dengan row-level locking untuk prevent race condition.
    with_for_update() akan lock row ini sampai commit, jadi request lain harus tunggu.

    IMPORTANT: Chat dibedakan berdasarkan:
    - Pribadi: phone (group_id=NULL)
    - Grup: group_id + participant_phone (1 chat per participant di setiap grup)
      Ini agar setiap orang yang chat di grup jadi antrian terpisah.

    Args:
        phone: Customer phone number (untuk private)
        name: Customer name (untuk private) atau participant name (untuk grup)
        group_id: WhatsApp group ID (e.g., 120363423035678646@g.us) if from group
        group_name: WhatsApp group name if available
        participant_jid: Participant JID for group messages (for auto-mention)
        participant_phone: Participant phone number (for group messages)
        participant_name: Participant name (for group messages)
    """
    if group_id:
        # GRUP: Cari berdasarkan group_id + participant_phone (1 chat per participant per grup)
        # Ini agar setiap orang di grup punya ticket terpisah
        chat = db.query(Chat).filter(
            Chat.group_id == group_id,
            Chat.customer_phone == participant_phone
        ).with_for_update().first()

        if chat:
            chat.online = True
            chat.last_message_at = datetime.now()
            # Update group name if provided
            if group_name:
                chat.group_name = group_name
            # Update participant name if provided (might change display name)
            if participant_name and chat.customer_name != participant_name:
                chat.customer_name = participant_name
                print(f"[CHAT UPDATE] Updated participant name to: {participant_name}")
            # Update last participant JID for auto-mention
            if participant_jid:
                chat.last_participant_jid = participant_jid
            db.commit()
            db.refresh(chat)
            return chat

        # Buat chat grup baru untuk participant ini
        new_chat = Chat(
            customer_name=participant_name or participant_phone or f"Anggota Grup",  # Nama participant
            customer_phone=participant_phone,  # Phone participant (bukan group ID)
            channel=ChatChannel.whatsapp,
            mode=ChatMode.bot,
            online=True,
            unread_count=0,
            last_message_at=datetime.now(),
            group_id=group_id,
            group_name=group_name,
            last_participant_jid=participant_jid,
        )
        print(f"[CHAT NEW] Creating new chat for participant {participant_phone} in group {group_name or group_id}")
    else:
        # PRIBADI: Cari berdasarkan phone dengan group_id NULL
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

        # Buat chat pribadi baru
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


# =========================
# MESSAGE
# =========================
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
    """Decode base64 media and save to uploads/ directory. Returns relative URL."""
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
    """
    Save customer message to database.

    Args:
        db: Database session
        chat: Chat object
        text: Message text
        participant_phone: Phone number of sender (for group messages)
        participant_name: Name of sender (for group messages)
        media_url: URL to saved media file
        media_type: Type of media (image, video, document, audio)
        media_filename: Original filename
    """
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


# =========================
# TICKET
# =========================
def get_or_create_ticket(db: Session, chat: Chat, priority: TicketPriority = TicketPriority.medium) -> Ticket:
    """
    Get or create ticket untuk chat.
    - Jika sudah ada ticket AKTIF (pending/assigned/in_progress/waiting_customer/escalated), return yang ada
    - Jika ticket sudah resolved/closed, BUAT BARU (karena ini percakapan baru)
    - Jika belum ada sama sekali, buat yang baru

    IMPORTANT: Karena database constraint 1 chat = 1 ticket, kita harus DELETE ticket lama
    sebelum buat yang baru (atau update ticket yang sudah ada)
    """
    # Check apakah sudah punya ticket
    ticket = db.query(Ticket).filter(Ticket.chat_id == chat.id).first()

    if ticket:
        # Jika ticket masih AKTIF (belum resolved/closed), return yang ada
        if ticket.status not in [TicketStatus.resolved, TicketStatus.closed]:
            return ticket

        # Jika ticket sudah RESOLVED/CLOSED, buat baru dengan UPDATE existing ticket
        # (karena constraint 1 chat = 1 ticket, kita reuse ticket yang sama)
        print(f"[TICKET] Ticket #{ticket.id} sudah {ticket.status.value}, reset untuk percakapan baru")
        logger.info(f"[TICKET REOPEN] ticket_id={ticket.id} old_status={ticket.status.value}")

        # Reset ticket untuk percakapan baru
        ticket.status = TicketStatus.pending
        ticket.priority = priority
        ticket.assigned_agent_id = None
        ticket.created_at = datetime.now()
        ticket.assigned_at = None
        ticket.first_response_at = None
        ticket.resolved_at = None
        ticket.notes = None
        ticket.tags = None

        # Reset chat mode ke bot (agar bot bisa balas lagi)
        chat.mode = ChatMode.bot
        chat.assigned_agent_id = None

        db.commit()
        db.refresh(ticket)

        print(f"[TICKET] ✅ Reopened ticket #{ticket.id} for chat #{chat.id} (priority={priority.value})")
        logger.info(f"[TICKET REOPENED] ticket_id={ticket.id} chat_id={chat.id} priority={priority.value}")

        return ticket

    # Kalau tidak ada ticket sama sekali, buat BARU
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

    print(f"[TICKET] ✅ Created new ticket #{new_ticket.id} for chat #{chat.id} (priority={priority.value})")
    logger.info(f"[TICKET CREATED] ticket_id={new_ticket.id} chat_id={chat.id} priority={priority.value}")

    return new_ticket


# =========================
# WEBHOOK
# =========================
@router.post("/webhook/baileys")
async def whapi_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    print("[WEBHOOK] ===== WEBHOOK RECEIVED =====")  # DEBUG: Direct print
    logger.info(f"[WEBHOOK RECEIVED] Headers: {dict(request.headers)}")
    try:
        data = await request.json()
        print(f"[WEBHOOK] Data received: {data}")  # DEBUG: Direct print
        logger.info(f"[WEBHOOK DATA] {data}")
    except Exception as e:
        print(f"[WEBHOOK] Error parsing JSON: {e}")  # DEBUG: Direct print
        logger.error(f"[WEBHOOK ERROR] Failed to parse JSON: {e}")
        raise HTTPException(status_code=400, detail="invalid json")

    # 🔍 DEBUG: Check if this is Baileys format (single message) or WHAPI format (messages array)
    if "from" in data and "text" in data:
        # Baileys format - single message object
        print(f"[WEBHOOK] Baileys format detected - converting to array")
        logger.info(f"[WEBHOOK] Baileys single message format")
        msgs = [data]  # Wrap in array
    elif "messages" in data:
        # WHAPI format - messages array
        msgs = data.get("messages")
    else:
        print(f"[WEBHOOK] Unknown format. Keys: {list(data.keys())}")
        logger.error(f"[WEBHOOK] Unknown format: {list(data.keys())}")
        return {"status": "ignored"}

    if not msgs:
        print(f"[WEBHOOK] No messages in data. Keys: {list(data.keys())}")  # DEBUG
        return {"status": "ignored"}

    print(f"[WEBHOOK] Processing {len(msgs)} messages")  # DEBUG
    logger.info(f"[WEBHOOK] Will process {len(msgs)} messages")

    for msg in msgs:
        try:
            print(f"[WEBHOOK MESSAGE] Keys: {list(msg.keys())}")  # DEBUG
            print(f"[WEBHOOK MESSAGE] Full msg: {msg}")  # DEBUG
            logger.info(f"[WEBHOOK MSG START] Processing message with keys: {list(msg.keys())}")

            sender_raw = msg.get("from")
            if not sender_raw:
                logger.warning("[WEBHOOK] No 'from' field in message")
                print(f"[WEBHOOK WARNING] No 'from' field, skipping")
                continue

            print(f"[WEBHOOK] sender_raw={sender_raw}")  # DEBUG

            is_group = sender_raw.endswith("@g.us")
            
            # Check mention dari isMentioned atau mentionedJid
            is_mentioned = msg.get("isMentioned", False)
            if not is_mentioned and msg.get("mentionedJid"):
                is_mentioned = len(msg.get("mentionedJid", [])) > 0
            
            # ALTERNATIVE: Check apakah text mengandung mention tag (dari baileys)
            if not is_mentioned:
                text_body = msg.get("text", {}).get("body") if isinstance(msg.get("text"), dict) else msg.get("text")
                if text_body and "@" in text_body and is_group:
                    is_mentioned = True  # Assume ada mention jika text ada @

            print(f"[WEBHOOK] is_group={is_group} is_mentioned={is_mentioned} from={sender_raw}")

            # 🔥 GROUP = HARUS MENTION
            if is_group and not is_mentioned:
                logger.info(f"[WEBHOOK SKIP] Group message tanpa mention dari {sender_raw}")
                continue

            # 📱 EXTRACT PHONE NUMBER & PARTICIPANT INFO
            # Untuk PRIVATE: gunakan sender JID langsung
            # Untuk GROUP: 1 chat per grup, simpan participant info di message
            participant_phone = None
            participant_name = None
            participant_jid = None  # For auto-mention when replying

            if is_group:
                # Ambil participant (pengirim asli di grup)
                # participant bisa berupa JID resolved atau raw dari Baileys
                participant_jid = msg.get("participant")
                if not participant_jid:
                    logger.warning(f"[WEBHOOK] Group message tanpa participant JID, skip")
                    print(f"[WEBHOOK WARNING] No participant for group message")
                    continue
                participant_phone = normalize_phone(participant_jid)
                # Prioritas nama: participantName > pushName > phone
                participant_name = msg.get("participantName") or msg.get("pushname") or msg.get("pushName") or participant_phone
                phone = None  # Untuk grup, tidak pakai phone sebagai identifier
                print(f"[WEBHOOK] GROUP: participant={participant_phone} ({participant_name}) group={sender_raw}")
                logger.info(f"[WEBHOOK GROUP] participant={participant_phone} name={participant_name} group={sender_raw}")
            else:
                # Private chat: gunakan sender langsung
                phone = normalize_phone(sender_raw)
                print(f"[WEBHOOK] PRIVATE: sender={sender_raw} → phone={phone}")

            sender_name = msg.get("pushname") or msg.get("pushName") or (phone or participant_phone)

            text = (
                msg.get("text", {}).get("body")
                if isinstance(msg.get("text"), dict)
                else msg.get("text")
            )

            print(f"[WEBHOOK] Extracted text: '{text}' (type={type(text).__name__})")  # DEBUG

            # Check if message has media (image, video, document, audio)
            has_media = bool(msg.get("mediaBase64") and msg.get("mediaType"))
            media_type_label = msg.get("mediaType", "").capitalize() if has_media else ""

            if not text and not has_media:
                print(f"[WEBHOOK] Skipping: text is empty/None and no media")  # DEBUG
                continue

            # If media-only message (no text/caption), use placeholder text
            if not text and has_media:
                text = f"[{media_type_label or 'Media'}]"
                print(f"[WEBHOOK] Media-only message, using placeholder: '{text}'")

            text = text.strip()
            print(f"[WEBHOOK] After strip: '{text}' is_group={is_group}")  # DEBUG

            # 🔄 DEDUPLICATION: Check apakah message ini duplicate (race condition)
            msg_timestamp = msg.get("timestamp") or msg.get("messageTimestamp")
            dedup_key = participant_phone if is_group else phone  # Use participant for groups
            if message_dedup_cache.is_duplicate(dedup_key, text, msg_timestamp):
                print(f"[WEBHOOK SKIP] Duplicate message detected: key={dedup_key} text='{text[:50]}'")
                logger.warning(f"[WEBHOOK SKIP DUPLICATE] key={dedup_key} text='{text[:30]}'")
                continue  # Skip duplicate message

            # Hapus mention tag dari text untuk bot processing
            # Contoh: "@128136708657329 bot halo" -> "bot halo"
            if is_group and text.startswith("@"):
                # Cari spasi pertama setelah @ (akhir dari mention tag)
                space_idx = text.find(" ")
                if space_idx != -1:
                    text = text[space_idx:].strip()
                    print(f"[WEBHOOK] Removed mention tag, text now: '{text}'")

            logger.info(
                f"[INCOMING] group={is_group} mentioned={is_mentioned} from={sender_raw} text='{text}'"
            )

            # 📱 SIMPAN INFO GRUP jika pesan dari grup
            # Ini penting agar agent tau ticket datang dari grup mana
            group_id = sender_raw if is_group else None
            group_name = msg.get("groupName") if is_group else None  # Get from Baileys payload

            if is_group:
                print(f"[WEBHOOK] Saving group info: group_id={group_id} group_name={group_name}")
                logger.info(f"[WEBHOOK GROUP INFO] group_id={group_id} group_name={group_name}")

            chat = get_or_create_chat(
                db, phone, sender_name,
                group_id=group_id,
                group_name=group_name,
                participant_jid=participant_jid,
                participant_phone=participant_phone,
                participant_name=participant_name
            )

            # Handle incoming media from WhatsApp
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
                    print(f"[WEBHOOK MEDIA] Saved incoming media: {incoming_media_url}")

            save_customer_message(
                db, chat, text,
                participant_phone=participant_phone,
                participant_name=participant_name,
                media_url=incoming_media_url,
                media_type=incoming_media_type,
                media_filename=incoming_media_filename,
            )

            # 🎫 OTOMATIS BUAT TICKET untuk semua message customer
            ticket = get_or_create_ticket(db, chat, priority=TicketPriority.medium)
            print(f"[TICKET] ticket_id={ticket.id} chat_id={chat.id} status={ticket.status.value}")

            # 🔒 ACQUIRE PER-CHAT LOCK untuk prevent concurrent processing
            # Jika chat ini sedang diproses oleh request lain, tunggu sampai selesai
            chat_lock = chat_processing_lock.get_lock(chat.id)

            with chat_lock:
                # Re-fetch chat status dalam lock untuk ensure consistency
                db.refresh(chat)

                # 🔄 AUTO-FIX: Sync chat.mode dengan ticket.status (fix inconsistent state)
                # Jika ticket status = pending/waiting_customer tapi mode = agent, reset ke bot
                if ticket.status in [TicketStatus.pending, TicketStatus.waiting_customer]:
                    if chat.mode != ChatMode.bot:
                        print(f"[AUTO-FIX] Inconsistent state: ticket={ticket.status.value} but mode={chat.mode.value}")
                        print(f"[AUTO-FIX] Resetting chat.mode to 'bot' for ticket #{ticket.id}")
                        logger.warning(f"[AUTO-FIX] chat_id={chat.id} ticket_id={ticket.id} old_mode={chat.mode.value} -> bot")
                        chat.mode = ChatMode.bot
                        chat.assigned_agent_id = None
                        db.commit()
                        db.refresh(chat)

                # ✅ CEK APAKAH BOT HARUS BALAS atau SKIP
                # Bot SKIP jika:
                # 1. chat.mode == 'agent' (ticket sudah diambil agent)
                # 2. chat.mode == 'paused' (chat dipause)
                # 3. chat.mode == 'closed' (chat ditutup) - seharusnya tidak terjadi karena get_or_create_ticket sudah reset
                #
                # Bot BALAS jika:
                # 1. chat.mode == 'bot' (default mode, bot aktif)

                # Private chat should always be eligible for bot processing.
                # Group chat still follows mode gate.
                should_bot_reply = (not is_group) or (chat.mode == ChatMode.bot)

                if not should_bot_reply:
                    print(f"[BOT SKIP] chat.mode={chat.mode.value} - Skip bot, message masuk ke agent queue")
                    logger.info(f"[BOT SKIP] chat_id={chat.id} mode={chat.mode.value} ticket_id={ticket.id}")
                    continue  # Skip bot processing, message sudah disimpan untuk agent

                # ✅ BOT PROCESSING:
                # Setelah pengecekan di atas, kita sudah tau:
                # - GROUP tanpa mention = sudah di-skip (line 190-193)
                # - GROUP dengan mention = LANJUT ke bot (jika mode=bot)
                # - PRIVATE (direct message) = LANJUT ke bot (jika mode=bot)
                # - Jika mode=agent = sudah di-skip (line di atas)

                if is_group:
                    print(f"[PROCESS GROUP] Group message WITH mention - processing bot (mode={chat.mode.value})")
                else:
                    print(f"[PROCESS PRIVATE] Private/Direct message - processing bot (mode={chat.mode.value})")  # DEBUG

                # Untuk group, pake group ID untuk handle_bot agar state terpisah
                # Untuk private, pake phone number
                bot_user_identifier = sender_raw if is_group else phone
                print(f"[BOT IDENTIFIER] bot_user={bot_user_identifier} is_group={is_group}")  # DEBUG

                logger.info(f"[BOT PROCESS] sender_raw={sender_raw} is_group={is_group} bot_user={bot_user_identifier}")
                try:
                    reply = handle_bot(bot_user_identifier, text)
                    print(f"[WEBHOOK] Bot reply: {reply}")
                    logger.info(f"[BOT RESPONSE] reply={reply}")
                except Exception as e:
                    print(f"[WEBHOOK ERROR] handle_bot failed: {e}")
                    logger.exception(f"[BOT ERROR] handle_bot failed: {e}")
                    continue

            # Lock released here - bot processing selesai

            if reply:
                print(f"[WEBHOOK] Got reply, processing...")
                logger.info(f"[BOT GOT REPLY] reply='{reply}'")
                
                # Get participant JID (pengirim pesan di grup)
                sender_jid = msg.get("participant")

                # Untuk private chat: reply tanpa mention
                # Untuk group chat: tambahkan @nama di awal text + mentions array
                if is_group:
                    # WhatsApp mention perlu: 1) @nama di text, 2) JID di mentions array
                    mention_name = participant_name or participant_phone or "User"
                    reply_text = f"@{mention_name} {reply}"
                    logger.info(f"[BOT GROUP] text='{reply_text}' mention_jid={sender_jid}")
                else:
                    reply_text = reply  # Private: tanpa mention
                    sender_jid = None
                    logger.info(f"[BOT PRIVATE] text='{reply_text}'")

                try:
                    save_bot_reply(db, chat, reply_text)
                    print(f"[WEBHOOK] Saved bot reply to DB")
                except Exception as e:
                    print(f"[WEBHOOK ERROR] Failed to save reply: {e}")
                    logger.exception(f"Failed to save bot reply: {e}")

                target = sender_raw if is_group else f"{phone}@c.us"
                mentions = [sender_jid] if sender_jid else None
                logger.info(f"[BOT SEND] target={target} mentions={mentions}")
                
                try:
                    background_tasks.add_task(send_text, target, reply_text, mentions)
                    print(f"[WEBHOOK] Task queued for sending")
                    logger.info(f"[BOT QUEUED] Task queued untuk send")

                    # ✅ MODE TETAP 'bot' sampai agent claim ticket
                    # Tidak perlu ubah mode di sini. Mode akan berubah ke 'agent' saat:
                    # 1. Agent claim ticket via queue (queue_service.agent_claim_ticket)
                    # 2. Auto-assign ke agent (queue_service.auto_assign_ticket)
                    # 3. Manual assign oleh admin (queue_service.manual_assign_ticket)
                    #
                    # Dengan begini, bot akan terus balas (grup & private) sampai agent ambil.

                except Exception as e:
                    print(f"[WEBHOOK ERROR] Failed to queue send task: {e}")
                    logger.exception(f"Failed to queue send task: {e}")
            else:
                print(f"[WEBHOOK] No reply from bot")
                logger.info(f"[BOT NO REPLY] No reply generated")
        except Exception as e:
            print(f"[WEBHOOK ERROR] Unexpected error processing message: {e}")
            logger.exception(f"[WEBHOOK ERROR] Unexpected error: {e}")

    return {"status": "ok"}
