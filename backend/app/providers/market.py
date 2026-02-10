from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol

try:
    import akshare as ak
except Exception:  # pragma: no cover
    ak = None


class MarketDataProvider(Protocol):
    def get_15m_bars(self, symbol: str, limit: int = 128) -> list[dict]: ...
    def get_daily_bars(self, symbol: str, limit: int = 120) -> list[dict]: ...


def _normalize_symbol(symbol: str) -> str:
    if symbol.startswith(("sh", "sz", "bj")):
        return symbol
    if symbol.startswith(("6", "9")):
        return f"sh{symbol}"
    if symbol.startswith(("8", "4")):
        return f"bj{symbol}"
    return f"sz{symbol}"


class AkShareMarketDataProvider:
    def get_15m_bars(self, symbol: str, limit: int = 128) -> list[dict]:
        if ak is None:
            return []
        secid = _normalize_symbol(symbol)
        try:
            df = ak.stock_zh_a_hist_min_em(symbol=secid, period="15", adjust="")
            if df is None or df.empty:
                return []
            records = []
            for _, row in df.tail(limit).iterrows():
                records.append(
                    {
                        "ts": row.get("时间"),
                        "open": float(row.get("开盘", 0)),
                        "high": float(row.get("最高", 0)),
                        "low": float(row.get("最低", 0)),
                        "close": float(row.get("收盘", 0)),
                        "volume": float(row.get("成交量", 0)),
                        "turnover": float(row.get("成交额", 0)),
                    }
                )
            return records
        except Exception:
            return []

    def get_daily_bars(self, symbol: str, limit: int = 120) -> list[dict]:
        if ak is None:
            return []
        secid = _normalize_symbol(symbol)
        start = (datetime.utcnow() - timedelta(days=360)).strftime("%Y%m%d")
        end = datetime.utcnow().strftime("%Y%m%d")
        try:
            df = ak.stock_zh_a_hist(symbol=secid, period="daily", start_date=start, end_date=end, adjust="")
            if df is None or df.empty:
                return []
            records = []
            for _, row in df.tail(limit).iterrows():
                records.append(
                    {
                        "ts": row.get("日期"),
                        "open": float(row.get("开盘", 0)),
                        "high": float(row.get("最高", 0)),
                        "low": float(row.get("最低", 0)),
                        "close": float(row.get("收盘", 0)),
                        "volume": float(row.get("成交量", 0)),
                        "turnover": float(row.get("成交额", 0)),
                    }
                )
            return records
        except Exception:
            return []
