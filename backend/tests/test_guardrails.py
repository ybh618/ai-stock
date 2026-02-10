from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.engine.guardrails import (
    apply_guardrails,
    has_enough_evidence,
    is_cooldown_hit,
    is_reversal_allowed,
)
from app.models.schemas import LlmOutput


def test_apply_guardrails_caps_position() -> None:
    output = LlmOutput(
        summary_zh="z",
        summary_en="e",
        action="buy",
        target_position_pct=99.0,
        evidence={"market_features": [{"a": 1}], "news_citations": [{"b": 1}]},
        confidence=0.8,
    )
    bounded = apply_guardrails(output, "conservative")
    assert bounded.target_position_pct <= 20


def test_has_enough_evidence() -> None:
    output = LlmOutput(
        summary_zh="z",
        summary_en="e",
        action="buy",
        target_position_pct=20.0,
        evidence={"market_features": [{"a": 1}], "news_citations": [{"b": 1}]},
        confidence=0.8,
    )
    assert has_enough_evidence(output)


def test_cooldown_hit() -> None:
    last = {"symbol": "600000", "action": "buy", "created_at": datetime.now(UTC) - timedelta(minutes=30)}
    assert is_cooldown_hit(last, "600000", "buy")


def test_reversal_requires_high_confidence() -> None:
    last = {"action": "buy"}
    assert not is_reversal_allowed(last, "sell", 0.5)
    assert is_reversal_allowed(last, "sell", 0.9)
