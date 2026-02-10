from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol

try:
    import akshare as ak
except Exception:  # pragma: no cover
    ak = None


class MarketDataProvider(Protocol):
    def get_15m_bars(self, symbol: str, limit: int = 128) -> list[dict]: ...
    def get_daily_bars(self, symbol: str, limit: int = 120) -> list[dict]: ...


def _normalize_symbol(symbol: str) -> str:
    return symbol.lower().strip()


def _candidate_symbols(symbol: str) -> list[str]:
    normalized = _normalize_symbol(symbol)
    raw = normalized
    if normalized.startswith(("sh", "sz", "bj")):
        raw = normalized[2:]
    candidates: list[str] = [raw]
    if raw.startswith(("6", "9")):
        candidates.append(f"sh{raw}")
    elif raw.startswith(("8", "4")):
        candidates.append(f"bj{raw}")
    else:
        candidates.append(f"sz{raw}")
    if normalized not in candidates:
        candidates.append(normalized)
    # 去重保持顺序
    return list(dict.fromkeys(candidates))


def _now_utc() -> datetime:
    return datetime.now(UTC)


class AkShareMarketDataProvider:
    def __init__(self) -> None:
        self.last_15m_symbol: str = ""
        self.last_daily_symbol: str = ""
        self.last_error: str = ""
        self.last_15m_from_5m: bool = False

    def get_15m_bars(self, symbol: str, limit: int = 128) -> list[dict]:
        if ak is None:
            self.last_error = "akshare not available"
            return []
        self.last_15m_symbol = ""
        self.last_error = ""
        self.last_15m_from_5m = False
        for candidate in _candidate_symbols(symbol):
            try:
                df = ak.stock_zh_a_hist_min_em(symbol=candidate, period="15", adjust="")
            except Exception as error:
                self.last_error = str(error)
                continue
            if df is None or df.empty:
                continue
            records: list[dict] = []
            for _, row in df.tail(limit).iterrows():
                records.append(
                    {
                        "ts": row.get("时间") or row.get("date") or row.get("日期"),
                        "open": float(row.get("开盘", 0) or 0),
                        "high": float(row.get("最高", 0) or 0),
                        "low": float(row.get("最低", 0) or 0),
                        "close": float(row.get("收盘", 0) or 0),
                        "volume": float(row.get("成交量", 0) or 0),
                        "turnover": float(row.get("成交额", 0) or 0),
                    }
                )
            if records:
                self.last_15m_symbol = candidate
                return records
        # Fallback: pull 5m bars and aggregate into 15m bars.
        for candidate in _candidate_symbols(symbol):
            try:
                df = ak.stock_zh_a_hist_min_em(symbol=candidate, period="5", adjust="")
            except Exception as error:
                self.last_error = str(error)
                continue
            if df is None or df.empty:
                continue
            records_5m: list[dict] = []
            for _, row in df.tail(limit * 3 + 12).iterrows():
                records_5m.append(
                    {
                        "ts": row.get("时间") or row.get("date") or row.get("日期"),
                        "open": float(row.get("开盘", 0) or 0),
                        "high": float(row.get("最高", 0) or 0),
                        "low": float(row.get("最低", 0) or 0),
                        "close": float(row.get("收盘", 0) or 0),
                        "volume": float(row.get("成交量", 0) or 0),
                        "turnover": float(row.get("成交额", 0) or 0),
                    }
                )
            records_15m = _aggregate_5m_to_15m(records_5m, limit)
            if records_15m:
                self.last_15m_symbol = candidate
                self.last_15m_from_5m = True
                return records_15m
        return []

    def get_daily_bars(self, symbol: str, limit: int = 120) -> list[dict]:
        if ak is None:
            self.last_error = "akshare not available"
            return []
        self.last_daily_symbol = ""
        self.last_error = ""
        start = (_now_utc() - timedelta(days=400)).strftime("%Y%m%d")
        end = _now_utc().strftime("%Y%m%d")
        for candidate in _candidate_symbols(symbol):
            try:
                df = ak.stock_zh_a_hist(
                    symbol=candidate,
                    period="daily",
                    start_date=start,
                    end_date=end,
                    adjust="",
                )
            except Exception as error:
                self.last_error = str(error)
                continue
            if df is None or df.empty:
                continue
            records: list[dict] = []
            for _, row in df.tail(limit).iterrows():
                records.append(
                    {
                        "ts": row.get("日期") or row.get("date"),
                        "open": float(row.get("开盘", 0) or 0),
                        "high": float(row.get("最高", 0) or 0),
                        "low": float(row.get("最低", 0) or 0),
                        "close": float(row.get("收盘", 0) or 0),
                        "volume": float(row.get("成交量", 0) or 0),
                        "turnover": float(row.get("成交额", 0) or 0),
                    }
                )
            if records:
                self.last_daily_symbol = candidate
                return records
        return []


def _aggregate_5m_to_15m(records_5m: list[dict], limit_15m: int) -> list[dict]:
    if len(records_5m) < 3:
        return []
    total = (len(records_5m) // 3) * 3
    start = len(records_5m) - total
    output: list[dict] = []
    for idx in range(start, len(records_5m), 3):
        chunk = records_5m[idx : idx + 3]
        if len(chunk) < 3:
            continue
        output.append(
            {
                "ts": chunk[-1]["ts"],
                "open": chunk[0]["open"],
                "high": max(item["high"] for item in chunk),
                "low": min(item["low"] for item in chunk),
                "close": chunk[-1]["close"],
                "volume": sum(item["volume"] for item in chunk),
                "turnover": sum(item["turnover"] for item in chunk),
            }
        )
    return output[-limit_15m:]
