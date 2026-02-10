from __future__ import annotations

from app.engine.prefilter import prefilter_candidate


def _bars_15m(length: int = 80, close: float = 10.0, volume: float = 1000.0):
    bars = []
    for idx in range(length):
        bars.append(
            {
                "close": close + idx * 0.01,
                "volume": volume + idx * 5,
            }
        )
    return bars


def _bars_daily(length: int = 90, turnover: float = 200000000.0):
    return [{"close": 10.0 + idx * 0.02, "turnover": turnover} for idx in range(length)]


def test_prefilter_blocks_low_turnover():
    market = {
        "last_close_15m": 10.1,
        "ma20_15m": 10.0,
        "rsi14_15m": 40.0,
        "recent_high_32": 10.1,
        "vol_ratio_15m": 2.0,
        "turnover_20d_avg": 10.0,
        "daily_uptrend": True,
        "drawdown_32": 0.01,
    }
    result = prefilter_candidate(
        symbol="600000",
        name="浦发银行",
        market=market,
        bars_15m=_bars_15m(),
        bars_daily=_bars_daily(),
        news_items=[],
        risk_profile="neutral",
    )
    assert not result.triggered
    assert "low_turnover" in result.reasons


def test_prefilter_triggers_buy_breakout():
    market = {
        "last_close_15m": 12.0,
        "ma20_15m": 10.0,
        "rsi14_15m": 55.0,
        "recent_high_32": 12.0,
        "vol_ratio_15m": 2.0,
        "turnover_20d_avg": 300000000.0,
        "daily_uptrend": True,
        "drawdown_32": 0.02,
    }
    result = prefilter_candidate(
        symbol="600000",
        name="浦发银行",
        market=market,
        bars_15m=_bars_15m(),
        bars_daily=_bars_daily(),
        news_items=[],
        risk_profile="neutral",
    )
    assert result.triggered
    assert result.action_hint == "buy"
