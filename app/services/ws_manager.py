"""
WebSocket Connection Manager
Manages per-chat WebSocket connections for real-time events (typing indicators, etc.)
"""
import logging
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # {chat_id: set of active WebSocket connections}
        self.connections: Dict[int, Set[WebSocket]] = {}

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


# Singleton shared across the app
manager = ConnectionManager()
