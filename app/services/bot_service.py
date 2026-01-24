import os
import time
from typing import Optional

# simple in-memory state stores; replace with persistent storage for production
user_state = {}
last_human_reply = {}


def _load_admins() -> set:
    raw = os.environ.get("WHAPI_ADMINS", "")
    return {p.strip() for p in raw.split(",") if p.strip()}


ADMINS = _load_admins()


def _generate_ai_reply(user: str, message: str) -> str:
    """Generate a reply using an external AI provider if available.

    Falls back to smart keyword-based responses for Warung Madura agent support.
    """
    try:
        import openai

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        openai.api_key = api_key
        prompt = (
            "You are a support assistant for Warung Madura agents. "
            "Agents may report issues about stock, payments, system errors, deliveries, or ask questions. "
            "Reply concisely, supportively, and professionally in Bahasa Indonesia. "
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
        return (
            "Terima kasih pesannya. Admin support akan segera membantu Anda. "
            "Untuk bantuan lebih cepat, ketik 'agent' untuk terhubung langsung dengan admin."
        )


def handle_bot(user: str, message: str) -> Optional[str]:
    """Handle incoming message from `user` and return a reply string or None.

    Behavior:
    - If sender is an admin and sends management commands, adjust state.
    - If user is in `AGENT` or `PAUSE`, return None to indicate no bot reply.
    - Otherwise, generate AI reply (or canned fallback).
    """
    msg = message.strip()
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
        # do not auto-reply when human recently handled
        return None

    # generate AI reply
    return _generate_ai_reply(user, message)
