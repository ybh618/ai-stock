from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings


POSITIVE_NEWS = {"positive"}
NEGATIVE_NEWS = {"negative"}


@dataclass(slots=True)
class PrefilterResult:
    triggered: bool
    action_hint: str
    reasons: list[str]
    score: float


def prefilter_candidate(
    symbol: str,
    name: str,
    market: dict,
    bars_15m: list[dict],
    bars_daily: list[dict],
    news_items: list[dict],
    risk_profile: str,
) -> PrefilterResult:
    reasons: list[str] = []
    score = 0.0

    if len(bars_15m) < 64 or len(bars_daily) < 60:
        return PrefilterResult(False, "hold", ["insufficient_data"], 0.0)

    if market["turnover_20d_avg"] < settings.min_turnover_20d:
        return PrefilterResult(False, "hold", ["low_turnover"], 0.0)

    positive_news = [item for item in news_items if item.get("sentiment_hint") in POSITIVE_NEWS]
    negative_news = [item for item in news_items if item.get("sentiment_hint") in NEGATIVE_NEWS]

    close_now = market["last_close_15m"]
    ma20 = market["ma20_15m"]
    vol_ratio = market["vol_ratio_15m"]
    drawdown_32 = market["drawdown_32"]
    rsi_15m = market["rsi14_15m"]
    recent_high = market["recent_high_32"]

    vol_threshold = _vol_threshold(risk_profile)
    drawdown_threshold = _drawdown_threshold(risk_profile)

    buy_breakout = close_now > ma20 and close_now >= recent_high and vol_ratio >= vol_threshold
    buy_reversal = rsi_15m <= 30 and vol_ratio >= max(1.2, vol_threshold - 0.3)
    buy_uptrend_pullback = market["daily_uptrend"] and close_now > ma20 and vol_ratio >= 1.2
    buy_event = bool(positive_news) and vol_ratio >= 1.1

    sell_breakdown = close_now < ma20 and vol_ratio >= 1.1
    sell_drawdown = drawdown_32 >= drawdown_threshold
    sell_event = bool(negative_news) and close_now < ma20

    if buy_breakout:
        reasons.append("buy_breakout")
        score += 2.0
    if buy_reversal:
        reasons.append("buy_reversal")
        score += 1.2
    if buy_uptrend_pullback:
        reasons.append("buy_uptrend_pullback")
        score += 1.0
    if buy_event:
        reasons.append("buy_event")
        score += 1.0

    if sell_breakdown:
        reasons.append("sell_breakdown")
        score += 2.0
    if sell_drawdown:
        reasons.append("sell_drawdown")
        score += 1.3
    if sell_event:
        reasons.append("sell_event")
        score += 1.0

    buy_score = sum(1 for reason in reasons if reason.startswith("buy_"))
    sell_score = sum(1 for reason in reasons if reason.startswith("sell_"))
    if buy_score == 0 and sell_score == 0:
        return PrefilterResult(False, "hold", reasons or ["no_signal"], 0.0)

    action_hint = "buy" if buy_score >= sell_score else "sell"
    return PrefilterResult(True, action_hint, reasons, score)


def _vol_threshold(risk_profile: str) -> float:
    return {
        "aggressive": 1.3,
        "neutral": 1.5,
        "conservative": 1.7,
    }.get(risk_profile, 1.5)


def _drawdown_threshold(risk_profile: str) -> float:
    return {
        "aggressive": 0.08,
        "neutral": 0.06,
        "conservative": 0.05,
    }.get(risk_profile, 0.06)
