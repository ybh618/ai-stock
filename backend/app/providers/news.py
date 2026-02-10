from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Protocol

import httpx


class NewsProvider(Protocol):
    async def get_recent_news(self, symbol: str, name: str, hours: int = 24) -> list[dict]: ...


POSITIVE_KWS = ["中标", "回购", "增持", "预增", "签署", "订单", "突破"]
NEGATIVE_KWS = ["立案", "处罚", "暴雷", "减持", "违约", "下修", "亏损"]


class ScrapingNewsProvider:
    def __init__(self, timeout_seconds: float = 10.0):
        self.timeout_seconds = timeout_seconds
        self.sources = [
            "https://finance.sina.com.cn",
            "https://finance.eastmoney.com",
            "https://finance.qq.com",
        ]

    async def get_recent_news(self, symbol: str, name: str, hours: int = 24) -> list[dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        queries = [symbol, name]
        articles: list[dict] = []
        async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=True) as client:
            for source in self.sources:
                for query in queries:
                    if not query:
                        continue
                    search_url = f"{source}/search?wd={query}"
                    try:
                        response = await client.get(search_url)
                    except Exception:
                        continue
                    if response.status_code >= 400:
                        continue
                    for item in _extract_candidates(response.text, source):
                        item["symbol"] = symbol
                        item["name"] = name
                        if _is_relevant(item, symbol, name):
                            item["sentiment_hint"] = _sentiment_hint(item["title"] + " " + item["snippet"])
                            if item["published_at"] >= cutoff.isoformat():
                                articles.append(item)
        return _dedupe_news(articles)


def _extract_candidates(html: str, source: str) -> list[dict]:
    links = re.findall(r'href="(https?://[^"]+)"[^>]*>([^<]{4,120})</a>', html)
    now = datetime.now(timezone.utc).isoformat()
    items: list[dict] = []
    for url, title in links[:30]:
        text = re.sub(r"\s+", " ", title).strip()
        if len(text) < 5:
            continue
        items.append(
            {
                "source": source,
                "url": url,
                "title": text,
                "snippet": text[:120],
                "published_at": now,
            }
        )
    return items


def _dedupe_news(items: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    output: list[dict] = []
    for item in items:
        key = (item["source"], item["title"])
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def _is_relevant(item: dict, symbol: str, name: str) -> bool:
    hay = f"{item.get('title', '')} {item.get('snippet', '')}"
    return symbol in hay or (name and name in hay)


def _sentiment_hint(text: str) -> str:
    if any(k in text for k in POSITIVE_KWS):
        return "positive"
    if any(k in text for k in NEGATIVE_KWS):
        return "negative"
    return "neutral"
