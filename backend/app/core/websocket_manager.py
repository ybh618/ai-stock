from __future__ import annotations

import asyncio
from collections import defaultdict

from fastapi import WebSocket


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, client_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections[client_id].add(websocket)

    async def disconnect(self, client_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            if client_id in self._connections:
                self._connections[client_id].discard(websocket)
                if not self._connections[client_id]:
                    del self._connections[client_id]

    async def send_event(self, client_id: str, event_type: str, payload: dict) -> None:
        async with self._lock:
            sockets = list(self._connections.get(client_id, set()))
        if not sockets:
            return
        envelope = {"type": event_type, "payload": payload}
        dead: list[WebSocket] = []
        for socket in sockets:
            try:
                await socket.send_json(envelope)
            except Exception:
                dead.append(socket)
        if dead:
            async with self._lock:
                for socket in dead:
                    self._connections[client_id].discard(socket)
                if not self._connections[client_id]:
                    self._connections.pop(client_id, None)

    async def broadcast_event(self, event_type: str, payload: dict) -> None:
        async with self._lock:
            client_ids = list(self._connections.keys())
        for client_id in client_ids:
            await self.send_event(client_id, event_type, payload)

    async def is_online(self, client_id: str) -> bool:
        async with self._lock:
            return bool(self._connections.get(client_id))

    async def online_clients_count(self) -> int:
        async with self._lock:
            return len(self._connections)
