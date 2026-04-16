"""
WebSocket Connection Manager
Manages per-chat WebSocket connections for real-time events (typing indicators, etc.)
Also manages a global channel for broadcasting agent status changes.
"""
import logging
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # {chat_id: set of active WebSocket connections}
        self.connections: Dict[int, Set[WebSocket]] = {}
        # Global channel — untuk broadcast agent status ke semua dashboard client
        self.global_connections: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket, chat_id: int):
        await ws.accept()
        if chat_id not in self.connections:
            self.connections[chat_id] = set()
        self.connections[chat_id].add(ws)
        logger.info(f"[WS] Connected chat_id={chat_id} total={len(self.connections[chat_id])}")

    def disconnect(self, ws: WebSocket, chat_id: int):
        if chat_id in self.connections:
            self.connections[chat_id].discard(ws)
            if not self.connections[chat_id]:
                del self.connections[chat_id]
        logger.info(f"[WS] Disconnected chat_id={chat_id}")

    async def broadcast(self, chat_id: int, data: dict, exclude: WebSocket = None):
        """Broadcast a JSON payload to all clients connected to a chat."""
        if chat_id not in self.connections:
            logger.warning(f"[WS] Broadcast dropped — no clients for chat_id={chat_id}")
            return
        logger.warning(f"[WS] Broadcasting to chat_id={chat_id} clients={len(self.connections[chat_id])} data={data}")
        dead: Set[WebSocket] = set()
        for ws in self.connections[chat_id]:
            if ws is exclude:
                continue
            try:
                await ws.send_json(data)
            except Exception as e:
                logger.warning(f"[WS] Send failed chat_id={chat_id}: {e}")
                dead.add(ws)
        for ws in dead:
            self.connections[chat_id].discard(ws)

    def has_connections(self, chat_id: int) -> bool:
        return chat_id in self.connections and bool(self.connections[chat_id])

    # ── Global channel (agent status) ──────────────────────────────────────

    async def connect_global(self, ws: WebSocket):
        """Sambungkan client ke global channel (agent status)."""
        await ws.accept()
        self.global_connections.add(ws)
        logger.info(f"[WS-GLOBAL] Connected total={len(self.global_connections)}")

    def disconnect_global(self, ws: WebSocket):
        self.global_connections.discard(ws)
        logger.info(f"[WS-GLOBAL] Disconnected total={len(self.global_connections)}")

    async def broadcast_global(self, data: dict):
        """Broadcast payload ke semua client di global channel."""
        dead: Set[WebSocket] = set()
        for ws in list(self.global_connections):
            try:
                await ws.send_json(data)
            except Exception as e:
                logger.warning(f"[WS-GLOBAL] Send failed: {e}")
                dead.add(ws)
        for ws in dead:
            self.global_connections.discard(ws)
        logger.info(f"[WS-GLOBAL] Broadcast data={data} to {len(self.global_connections)} clients")


# Singleton shared across the app
manager = ConnectionManager()
