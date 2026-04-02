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


def _generate_external_api_reply(message: str, user: str = None) -> tuple:
    api_url = os.environ.get("BOT_REPLY_API_URL") or os.environ.get("API_CHAT_BOT")
    if not api_url:
        return None, False

    timeout_raw = os.environ.get("BOT_REPLY_API_TIMEOUT_SECONDS", "15")
    try:
        timeout_seconds = int(timeout_raw)
    except ValueError:
        timeout_seconds = 15

    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("BOT_REPLY_API_KEY") or os.environ.get("API_CHAT_BOT_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # Build payload: query + mode + sessionId (empty string on first message)
    payload: dict = {
        "query": message,
        "mode": "mpstore",
        "sessionId": user_sessions.get(user, "") if user else "",
    }

    try:
        response = requests.post(
            api_url,
            json=payload,
            headers=headers,
            timeout=timeout_seconds,
        )

        if response.status_code >= 400:
            return None, True  # HTTP error → treat as error

        try:
            data = response.json()
        except ValueError:
            data = response.text

        # Store sessionId if API returned one (for conversation context on next request)
        if isinstance(data, dict) and "sessionId" in data and user:
            new_session = data["sessionId"]
            if new_session:
                user_sessions[user] = new_session

        extracted = _extract_reply(data)
        if not extracted:
            return None, False  # API responded but no answer — not an error

        return extracted, False

    except requests.exceptions.Timeout:
        return None, True  # Timeout → treat as error
    except Exception:
        return None, True  # Any other exception → treat as error


def _generate_ai_reply(user: str, message: str, is_group: bool = False) -> Optional[str]:
   
    reply, _ = _generate_external_api_reply(message, user=user)
    return reply


def handle_bot(user: str, message: str) -> Optional[str]:
    msg = message.strip()
    is_private = not user.endswith("@g.us")  # Private if NOT ending with @g.us

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
            return None
        # Generate reply — tries external API first, then keyword fallback
        reply = _generate_ai_reply(user, msg, is_group=False)
        return reply

    # ✅ GROUP CHAT: Apply state machine
    state = user_state.get(user, "BOT")
    lower = msg.lower()
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
        return None

    # if a human recently replied for this user, prefer human flow (no AI)
    last = last_human_reply.get(user)
    if last and time.time() - last < 60 * 60:  # 1 hour window
        return None

    # Generate reply — tries external API first, then keyword fallback
    return _generate_ai_reply(user, msg, is_group=True)
