from __future__ import annotations

from app.models.schemas import WsEnvelope


def test_ws_envelope_allows_ping_without_payload() -> None:
    envelope = WsEnvelope.model_validate({"type": "ping"})
    assert envelope.type == "ping"
    assert envelope.payload == {}
