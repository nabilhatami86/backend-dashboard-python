"""
WebSocket route for real-time chat events (typing indicators).

Endpoint: ws://backend/ws/{chat_id}

Events sent from backend → frontend:
  {"type": "typing", "sender": "customer", "is_typing": true}

Events sent from frontend → backend:
  {"type": "typing", "is_typing": true}   ← agent is typing
  → backend forwards to Baileys /send-presence so customer sees typing indicator
"""
import asyncio
import logging
import requests
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.ws_manager import manager
from app.config.confiq_whapi import settings

logger = logging.getLogger(__name__)
router = APIRouter()


def _send_presence_sync(customer_jid: str, is_typing: bool):
    """Sync call to Baileys /send-presence (run in thread to avoid blocking event loop)."""
    status = "composing" if is_typing else "paused"
    resp = requests.post(
        f"{settings.BAILEYS_SERVICE_URL}/send-presence",
        json={"to": customer_jid, "status": status},
        headers={"x-api-key": settings.BAILEYS_API_KEY},
        timeout=5,
    )
    if not resp.ok:
        logger.warning(f"[WS] send-presence failed: {resp.status_code} {resp.text} jid={customer_jid}")


def _subscribe_presence_sync(customer_jid: str):
    """Sync call to Baileys /subscribe-presence so we receive presence.update events."""
    requests.post(
        f"{settings.BAILEYS_SERVICE_URL}/subscribe-presence",
        json={"jid": customer_jid},
        headers={"x-api-key": settings.BAILEYS_API_KEY},
        timeout=5,
    )


async def _notify_presence_to_wa(customer_jid: str, is_typing: bool):
    """Call Baileys /send-presence so customer sees agent typing indicator in WA."""
    if not settings.BAILEYS_SERVICE_URL:
        return
    try:
        await asyncio.to_thread(_send_presence_sync, customer_jid, is_typing)
    except Exception as e:
        logger.warning(f"[WS] Failed to send presence to Baileys: {e}")


async def _subscribe_presence(customer_jid: str):
    """Subscribe to customer presence so Baileys fires presence.update events."""
    if not settings.BAILEYS_SERVICE_URL:
        return
    try:
        await asyncio.to_thread(_subscribe_presence_sync, customer_jid)
        logger.info(f"[WS] Subscribed to presence for {customer_jid}")
    except Exception as e:
        logger.warning(f"[WS] Failed to subscribe presence: {e}")


@router.websocket("/ws/agents")
async def websocket_agent_status(ws: WebSocket):
    """
    Global WebSocket channel untuk menerima update status agent secara real-time.
    Frontend connect ke sini untuk mendapatkan event:
      {"type": "agent_status", "agent_id": 1, "name": "...", "display_name": "...", "status": "online", "is_available": true}
    """
    await manager.connect_global(ws)
    try:
        while True:
            # Koneksi ini hanya menerima event dari server, tidak mengirim
            # Tetap buka loop agar koneksi tidak putus
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_global(ws)
    except Exception as e:
        logger.exception(f"[WS-GLOBAL] Unexpected error: {e}")
        manager.disconnect_global(ws)


@router.websocket("/ws/{chat_id}")
async def websocket_typing(ws: WebSocket, chat_id: int):
    # Look up customer phone/group for this chat (needed for WA presence)
    customer_jid: str | None = None
    presence_jid: str | None = None 
    is_group_chat: bool = False
    from app.config.database import SessionLocal
    from app.models.chat import Chat
    db = SessionLocal()
    try:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if chat:
            if chat.group_id:
                # Grup: subscribe presence ke group JID agar dapat presence semua member
                # Agent typing dikirim ke group JID (WhatsApp protocol: presence bersifat global per-JID,
               
                is_group_chat = True
                presence_jid = chat.group_id
                customer_jid = chat.group_id
            elif chat.customer_phone:
                # Private chat: subscribe ke participant JID
                raw = chat.customer_phone.replace("@c.us", "").replace("@s.whatsapp.net", "")
                customer_jid = f"{raw}@c.us"
                presence_jid = customer_jid
    finally:
        db.close()

    await manager.connect(ws, chat_id)

    # Subscribe to customer presence so Baileys fires presence.update events
    # (required for customer typing indicator to appear in dashboard)
    if presence_jid:
        await _subscribe_presence(presence_jid)

    try:
        while True:
            data = await ws.receive_json()
            if data.get("type") == "typing" and customer_jid:
                await _notify_presence_to_wa(customer_jid, data.get("is_typing", False))
    except WebSocketDisconnect:
        manager.disconnect(ws, chat_id)
    except Exception as e:
        logger.exception(f"[WS] Unexpected error chat_id={chat_id}: {e}")
        manager.disconnect(ws, chat_id)
