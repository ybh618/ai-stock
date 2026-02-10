from __future__ import annotations

from app.engine.indicators import moving_average, rsi


def extract_market_features(symbol: str, bars_15m: list[dict], bars_daily: list[dict]) -> dict:
    closes_15m = [float(item.get("close", 0.0)) for item in bars_15m]
    volume_15m = [float(item.get("volume", 0.0)) for item in bars_15m]
    turnover_daily = [float(item.get("turnover", 0.0)) for item in bars_daily]
    closes_daily = [float(item.get("close", 0.0)) for item in bars_daily]

    ma20_15m = moving_average(closes_15m, 20)
    ma20_daily = moving_average(closes_daily, 20)
    ma60_daily = moving_average(closes_daily, 60)
    rsi14_15m = rsi(closes_15m, 14)

    last_close = closes_15m[-1] if closes_15m else 0.0
    last_ma20_15m = ma20_15m[-1] if ma20_15m else 0.0
    last_rsi_15m = rsi14_15m[-1] if rsi14_15m else 50.0
    recent_high_32 = max(closes_15m[-32:]) if closes_15m else 0.0
    vol_avg_20 = sum(volume_15m[-20:]) / max(1, len(volume_15m[-20:]))
    vol_ratio = (volume_15m[-1] / vol_avg_20) if volume_15m and vol_avg_20 > 0 else 0.0
    turnover_20d_avg = sum(turnover_daily[-20:]) / max(1, len(turnover_daily[-20:]))

    daily_uptrend = bool(ma20_daily and ma60_daily and ma20_daily[-1] > ma60_daily[-1])
    drawdown_32 = ((recent_high_32 - last_close) / recent_high_32) if recent_high_32 > 0 else 0.0

    return {
        "symbol": symbol,
        "last_close_15m": last_close,
        "ma20_15m": last_ma20_15m,
        "rsi14_15m": last_rsi_15m,
        "recent_high_32": recent_high_32,
        "vol_ratio_15m": vol_ratio,
        "turnover_20d_avg": turnover_20d_avg,
        "daily_uptrend": daily_uptrend,
        "drawdown_32": drawdown_32,
        "features": [
            {"name": "last_close_15m", "value": last_close},
            {"name": "ma20_15m", "value": last_ma20_15m},
            {"name": "rsi14_15m", "value": last_rsi_15m},
            {"name": "vol_ratio_15m", "value": vol_ratio},
            {"name": "turnover_20d_avg", "value": turnover_20d_avg},
            {"name": "drawdown_32", "value": drawdown_32},
            {"name": "daily_uptrend", "value": daily_uptrend},
        ],
    }
