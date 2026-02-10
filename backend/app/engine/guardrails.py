from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.models.schemas import LlmOutput


def apply_guardrails(output: LlmOutput, risk_profile: str) -> LlmOutput:
    max_position = _max_position(risk_profile)
    bounded = max(0.0, min(output.target_position_pct, float(max_position)))
    output.target_position_pct = bounded
    return output


def has_enough_evidence(output: LlmOutput) -> bool:
    evidence = output.evidence or {}
    market_features = evidence.get("market_features", []) or []
    news_citations = evidence.get("news_citations", []) or []
    return len(market_features) + len(news_citations) >= settings.evidence_min_items


def is_cooldown_hit(last_recommendation: dict | None, symbol: str, action: str) -> bool:
    if not last_recommendation:
        return False
    if last_recommendation.get("symbol") != symbol:
        return False
    if last_recommendation.get("action") != action:
        return False
    last_time = last_recommendation.get("created_at")
    if not isinstance(last_time, datetime):
        return False
    if last_time.tzinfo is None:
        last_time = last_time.replace(tzinfo=UTC)
    return datetime.now(UTC) - last_time < timedelta(minutes=settings.cooldown_minutes)


def is_reversal_allowed(last_recommendation: dict | None, action: str, confidence: float) -> bool:
    if not last_recommendation:
        return True
    previous_action = last_recommendation.get("action")
    if previous_action == action:
        return True
    if previous_action not in {"buy", "sell"} or action not in {"buy", "sell"}:
        return True
    return confidence >= 0.75


def _max_position(risk_profile: str) -> int:
    if risk_profile == "aggressive":
        return settings.max_position_aggressive
    if risk_profile == "conservative":
        return settings.max_position_conservative
    return settings.max_position_neutral
