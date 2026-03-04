import os
import time
from typing import Optional
import requests
from dotenv import load_dotenv

# Ensure .env is loaded even when this module is used standalone
load_dotenv()

# simple in-memory state stores; replace with persistent storage for production
user_state = {}
last_human_reply = {}
# Session IDs per user for stateful chatbot APIs (e.g., RAG-based APIs that return sessionId)
user_sessions: dict = {}


def _load_admins() -> set:
    raw = os.environ.get("WHAPI_ADMINS", "")
    return {p.strip() for p in raw.split(",") if p.strip()}


ADMINS = _load_admins()


def _has_external_api_config() -> bool:
    return bool(os.environ.get("BOT_REPLY_API_URL") or os.environ.get("API_CHAT_BOT"))


def _is_no_answer_response(text: str) -> bool:
    normalized = " ".join(text.lower().strip().split())
    # Strict match only: avoid false positives on helpful long responses
    no_answer_exact = {
        "no relevant documents found",
        "no relevant information found",
        "i could not find relevant documents",
        "i couldn't find relevant documents",
        "tidak ada dokumen relevan",
        "tidak ditemukan dokumen relevan",
        "maaf, saya tidak menemukan informasi yang relevan",
    }
    return normalized in no_answer_exact


def _extract_reply(payload) -> Optional[str]:
    """Recursively extract reply text from API response payload."""
    if isinstance(payload, str):
        return payload.strip() or None
    if isinstance(payload, dict):
        for key in ["reply", "response", "answer", "message", "text", "result", "data"]:
            value = payload.get(key)
            parsed = _extract_reply(value)
            if parsed:
                return parsed
    if isinstance(payload, list):
        for item in payload:
            parsed = _extract_reply(item)
            if parsed:
                return parsed
    return None


def _generate_external_api_reply(message: str, user: str = None) -> Optional[str]:
    """Generate a reply from external API configured in environment variables.

    Maintains session per user (stores sessionId returned by API).

    Required env (one of):
    - BOT_REPLY_API_URL
    - API_CHAT_BOT

    Optional env:
    - BOT_REPLY_API_KEY (sent as Bearer token)
    - API_CHAT_BOT_KEY (sent as Bearer token)
    - BOT_REPLY_API_TIMEOUT_SECONDS (default: 15)
    """
    api_url = os.environ.get("BOT_REPLY_API_URL") or os.environ.get("API_CHAT_BOT")
    if not api_url:
        print("[BOT SERVICE] No external API URL configured (BOT_REPLY_API_URL / API_CHAT_BOT)")
        return None

    timeout_raw = os.environ.get("BOT_REPLY_API_TIMEOUT_SECONDS", "15")
    try:
        timeout_seconds = int(timeout_raw)
    except ValueError:
        timeout_seconds = 15

    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("BOT_REPLY_API_KEY") or os.environ.get("API_CHAT_BOT_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # Build payload using {"query": message} — the format confirmed working by Postman test
    # Include sessionId if we have one for this user (maintains conversation context)
    payload: dict = {"query": message}
    if user and user in user_sessions:
        payload["sessionId"] = user_sessions[user]
        print(f"[BOT SERVICE] Using existing session for user={user} sessionId={user_sessions[user]}")

    try:
        response = requests.post(
            api_url,
            json=payload,
            headers=headers,
            timeout=timeout_seconds,
        )
        print(
            f"[BOT SERVICE] external_api status={response.status_code} "
            f"url={api_url} payload_keys={list(payload.keys())}"
        )

        if response.status_code >= 400:
            snippet = (response.text or "")[:300]
            print(
                f"[BOT SERVICE] external_api non-2xx status={response.status_code} "
                f"body='{snippet}'"
            )
            return None

        try:
            data = response.json()
        except ValueError:
            data = response.text

        # Store sessionId if API returned one (for conversation context on next request)
        if isinstance(data, dict) and "sessionId" in data and user:
            new_session = data["sessionId"]
            if new_session:
                user_sessions[user] = new_session
                print(f"[BOT SERVICE] Session stored/updated for user={user} sessionId={new_session}")

        extracted = _extract_reply(data)
        if not extracted:
            print("[BOT SERVICE] external_api response parsed but empty/no useful content")
            return None

        if _is_no_answer_response(extracted):
            print("[BOT SERVICE] external_api no relevant answer, skip reply")
            return None

        return extracted

    except requests.exceptions.Timeout:
        print(f"[BOT SERVICE] external_api request timed out after {timeout_seconds}s")
        return None
    except Exception as e:
        print(f"[BOT SERVICE] external_api request failed: {e}")
        return None


def _generate_ai_reply(user: str, message: str, is_group: bool = False) -> Optional[str]:
    """Generate a reply using an external AI provider if available.

    Falls back to smart keyword-based responses for Warung Madura agent support.

    Args:
        user: User identifier
        message: Message content
        is_group: True if message from group, False if private chat
    """
    # Priority 1: external API from env (payload: {"query": "<message>"})
    if _has_external_api_config():
        reply = _generate_external_api_reply(message, user=user)
        if reply:
            return reply
        # External API failed/no answer — fall through to keyword fallback

    try:
        import openai

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        openai.api_key = api_key
        context = "grup WhatsApp" if is_group else "chat pribadi"
        prompt = (
            "You are a support assistant for Warung Madura agents. "
            "Agents may report issues about stock, payments, system errors, deliveries, or ask questions. "
            f"Reply concisely, supportively, and professionally in Bahasa Indonesia via {context}. "
            f"Agent message: \"{message}\""
        )
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": "Warung Madura support assistant."},
                      {"role": "user", "content": prompt}],
            max_tokens=250,
            temperature=0.2,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        # Smart fallback based on keywords for Warung Madura scenarios
        msg_lower = message.lower()

        # Media message keywords (image, video, document, audio, sticker)
        if any(keyword in msg_lower for keyword in ["[image]", "[video]", "[audio]", "[document]", "[sticker]", "[media]"]):
            return (
                "Terima kasih, kami sudah menerima file yang Anda kirim. "
                "Admin akan segera memeriksa dan menghubungi Anda."
            )

        # Stock-related keywords
        if any(keyword in msg_lower for keyword in ["stock", "stok", "habis", "kosong", "restock", "barang"]):
            return (
                "Baik, saya catat masalah stock Anda. Untuk restock biasanya 1-2 hari kerja. "
                "Admin akan segera membantu koordinasi stock Anda."
            )

        # Payment-related keywords
        if any(keyword in msg_lower for keyword in ["bayar", "pembayaran", "transfer", "uang", "belum masuk"]):
            return (
                "Terima kasih laporannya. Tim admin akan segera cek transaksi pembayaran Anda. "
                "Mohon tunggu sebentar."
            )

        # System/Technical error keywords
        if any(keyword in msg_lower for keyword in ["error", "sistem", "gak bisa", "tidak bisa", "rusak", "bermasalah"]):
            return (
                "Maaf atas kendalanya. Tim teknis akan segera memeriksa masalah sistem Anda. "
                "Mohon tunggu max 15 menit."
            )

        # Delivery/shipping keywords
        if any(keyword in msg_lower for keyword in ["kirim", "pengiriman", "telat", "terlambat", "belum sampai"]):
            return (
                "Mohon maaf atas keterlambatan pengiriman. Admin akan koordinasi dengan tim logistik "
                "dan segera menghubungi Anda."
            )

        # Promo/promotion keywords
        if any(keyword in msg_lower for keyword in ["promo", "diskon", "promosi", "potongan"]):
            return (
                "Untuk info promo terbaru, admin akan segera informasikan ke Anda. "
                "Terima kasih sudah bertanya."
            )

        # Complaint keywords
        if any(keyword in msg_lower for keyword in ["komplain", "keluhan", "kecewa", "marah"]):
            return (
                "Mohon maaf atas ketidaknyamanan yang Anda alami. Admin akan segera menghubungi "
                "dan membantu menyelesaikan masalah ini."
            )

        # Default generic support response
        return "Terima kasih, pesan Anda telah kami terima. Admin akan segera membantu."


def handle_bot(user: str, message: str) -> Optional[str]:
    """Handle incoming message from `user` and return a reply string or None.

    Behavior:
    - If sender is an admin and sends management commands, adjust state.
    - PRIVATE CHAT (user without @g.us): ALWAYS generate AI reply (bot tidak pernah di-skip untuk private)
    - GROUP CHAT (user with @g.us): If user is in `AGENT` or `PAUSE`, return None to indicate no bot reply.
    - Otherwise, generate AI reply (or canned fallback).
    """
    msg = message.strip()
    is_private = not user.endswith("@g.us")  # Private if NOT ending with @g.us

    print(f"[BOT SERVICE] user={user} is_private={is_private} msg='{msg[:50]}'")  # DEBUG

    # admin commands: assign/unassign/reply
    if user in ADMINS:
        parts = msg.split(maxsplit=2)
        cmd = parts[0].lower() if parts else ""
        if cmd == "assign" and len(parts) >= 2:
            target = parts[1]
            user_state[target] = "AGENT"
            return f"Assigned agent for {target}."
        if cmd == "unassign" and len(parts) >= 2:
            target = parts[1]
            user_state[target] = "BOT"
            return f"Unassigned agent for {target}."
        if cmd == "reply" and len(parts) >= 3:
            target = parts[1]
            text = parts[2]
            # record that admin replied for the target so subsequent messages use human
            last_human_reply[target] = time.time()
            # returning a special string lets the caller deliver the message
            return f"__ADMIN_REPLY__|{target}|{text}"
        # admins don't receive AI replies
        return None

    # ✅ PRIVATE CHAT: ALWAYS process bot, skip state/command checks
    if is_private:
        # Private messages bypass the state machine - always generate AI reply
        # Check if human recently replied (still apply 1-hour window)
        last = last_human_reply.get(user)
        if last and time.time() - last < 60 * 60:  # 1 hour window
            # do not auto-reply when human recently handled
            print(f"[BOT SERVICE] PRIVATE: Skipping (human replied recently)")  # DEBUG
            return None
        # Generate reply — tries external API first, then keyword fallback
        reply = _generate_ai_reply(user, msg, is_group=False)
        print(f"[BOT SERVICE] PRIVATE: Generated reply='{reply[:50] if reply else None}'")  # DEBUG
        return reply

    # ✅ GROUP CHAT: Apply state machine
    state = user_state.get(user, "BOT")
    lower = msg.lower()
    print(f"[BOT SERVICE] GROUP: state={state} lower='{lower[:30]}'")  # DEBUG
    if lower == "agent":
        user_state[user] = "AGENT"
        return None
    if lower == "pause":
        user_state[user] = "PAUSE"
        return "Bot dihentikan sementara."
    if lower == "bot":
        user_state[user] = "BOT"
        return "Bot diaktifkan kembali."

    if state in ["AGENT", "PAUSE"]:
        print(f"[BOT SERVICE] GROUP: Skipping (state={state})")  # DEBUG
        return None

    # if a human recently replied for this user, prefer human flow (no AI)
    last = last_human_reply.get(user)
    if last and time.time() - last < 60 * 60:  # 1 hour window
        # do not auto-reply when human recently handled
        print(f"[BOT SERVICE] GROUP: Skipping (human replied recently)")  # DEBUG
        return None

    # Generate reply — tries external API first, then keyword fallback
    reply = _generate_ai_reply(user, msg, is_group=True)
    print(f"[BOT SERVICE] GROUP: Generated reply='{reply[:50] if reply else None}'")  # DEBUG
    return reply
