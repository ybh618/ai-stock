from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.core.websocket_manager import WebSocketManager
from app.db.database import get_db
from app.db.repository import replace_watchlist, upsert_preferences
from app.models.schemas import (
    ClientHelloPayload,
    SyncStatePayload,
    WsEnvelope,
)


def build_ws_router(ws_manager: WebSocketManager) -> APIRouter:
    router = APIRouter(tags=["ws"])

    @router.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        client_id: str | None = None
        try:
            while True:
                message = await websocket.receive_json()
                try:
                    envelope = WsEnvelope.model_validate(message)
                except ValidationError:
                    await websocket.send_json(
                        {
                            "type": "server.error",
                            "payload": {"code": "invalid_envelope"},
                        }
                    )
                    continue
                if envelope.type == "client.hello":
                    hello = ClientHelloPayload.model_validate(envelope.payload)
                    client_id = hello.client_id
                    await ws_manager.connect(client_id, websocket)
                    await websocket.send_json(
                        {"type": "server.hello.ack", "payload": {"ok": True}}
                    )
                    continue
                if envelope.type == "client.sync_state":
                    state = SyncStatePayload.model_validate(envelope.payload)
                    with get_db() as db:
                        replace_watchlist(db, state.client_id, state.watchlist)
                        upsert_preferences(db, state.client_id, state.preferences)
                    await websocket.send_json(
                        {"type": "server.sync_state.ack", "payload": {"ok": True}}
                    )
                    continue
                if envelope.type == "ping":
                    await websocket.send_json({"type": "pong", "payload": {}})
                    continue
        except WebSocketDisconnect:
            pass
        finally:
            if client_id:
                await ws_manager.disconnect(client_id, websocket)

    return router
