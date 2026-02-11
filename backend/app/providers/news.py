from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html import unescape
from typing import Any, Protocol
from urllib.parse import quote_plus

import httpx


class NewsProvider(Protocol):
    async def get_recent_news(self, symbol: str, name: str, hours: int = 24) -> list[dict]: ...


POSITIVE_KWS = ["中标", "回购", "增持", "预增", "签署", "订单", "突破"]
NEGATIVE_KWS = ["立案", "处罚", "暴雷", "减持", "违约", "下修", "亏损"]


@dataclass(frozen=True, slots=True)
class _NewsSource:
    name: str
    base_url: str
    kind: str


class ScrapingNewsProvider:
    def __init__(self, timeout_seconds: float = 10.0):
        self.timeout_seconds = timeout_seconds
        self.sources = [
            _NewsSource(name="sina", base_url="https://finance.sina.com.cn", kind="sina_html"),
            _NewsSource(name="eastmoney", base_url="https://finance.eastmoney.com", kind="eastmoney_jsonp"),
            _NewsSource(name="qq", base_url="https://finance.qq.com", kind="qq_json"),
        ]
        self.default_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    async def get_recent_news(self, symbol: str, name: str, hours: int = 24) -> list[dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        queries = _build_queries(symbol, name)
        articles: list[dict] = []
        if not queries:
            return articles
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            follow_redirects=True,
            headers=self.default_headers,
        ) as client:
            for source in self.sources:
                for query in queries:
                    try:
                        items = await self._fetch_from_source(client, source, query)
                    except Exception:
                        continue
                    for item in items:
                        normalized = _normalize_item(item, source.base_url, symbol, name, cutoff)
                        if normalized:
                            articles.append(normalized)
        return _dedupe_news(articles)

    async def _fetch_from_source(self, client: httpx.AsyncClient, source: _NewsSource, query: str) -> list[dict]:
        if source.kind == "sina_html":
            return await self._fetch_sina_news(client, source, query)
        if source.kind == "eastmoney_jsonp":
            return await self._fetch_eastmoney_news(client, source, query)
        if source.kind == "qq_json":
            return await self._fetch_qq_news(client, source, query)
        return []

    async def _fetch_sina_news(self, client: httpx.AsyncClient, source: _NewsSource, query: str) -> list[dict]:
        search_url = f"https://search.sina.com.cn/?q={quote_plus(query)}&c=news&from=channel&ie=utf-8"
        response = await client.get(search_url, headers={"Referer": "https://search.sina.com.cn/"})
        if response.status_code >= 400:
            return []
        return _extract_sina_candidates(response.text, source.base_url)

    async def _fetch_eastmoney_news(self, client: httpx.AsyncClient, source: _NewsSource, query: str) -> list[dict]:
        payload = {
            "uid": "",
            "keyword": query,
            "type": ["cmsArticleWebOld"],
            "client": "web",
            "clientType": "web",
            "clientVersion": "curr",
            "param": {
                "cmsArticleWebOld": {
                    "searchScope": "default",
                    "sort": "default",
                    "pageIndex": 1,
                    "pageSize": 20,
                    "preTag": "<em>",
                    "postTag": "</em>",
                }
            },
        }
        response = await client.get(
            "https://search-api-web.eastmoney.com/search/jsonp",
            params={
                "cb": "jQuery_news",
                "param": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            },
            headers={"Referer": f"https://so.eastmoney.com/news/s?keyword={quote_plus(query)}"},
        )
        if response.status_code >= 400:
            return []
        return _extract_eastmoney_candidates(response.text, source.base_url)

    async def _fetch_qq_news(self, client: httpx.AsyncClient, source: _NewsSource, query: str) -> list[dict]:
        response = await client.post(
            "https://so.html5.qq.com/ajax/real/search_news",
            data={
                "pageIndex": 0,
                "cookieItem": "",
                "tabId": "0",
                "bigCardIndex": "",
                "conds": "",
                "filterUrl": "",
                "q": query,
                "token": "",
                "r": str(int(datetime.now(timezone.utc).timestamp() * 1000)),
                "updateQuery": "true",
                "adMessage": "",
            },
            headers={
                "Origin": "https://so.html5.qq.com",
                "Referer": f"https://so.html5.qq.com/page/real/search_news?word={quote_plus(query)}",
                "Accept": "application/json, text/plain, */*",
            },
        )
        if response.status_code >= 400:
            return []
        return _extract_qq_candidates(response.text, source.base_url)


def _extract_candidates(html: str, source: str) -> list[dict]:
    if "sina.com.cn" in source:
        return _extract_sina_candidates(html, source)
    return _extract_generic_html_candidates(html, source)


def _extract_sina_candidates(html: str, source: str) -> list[dict]:
    marker = r'<div class="box-result'
    indices = [m.start() for m in re.finditer(marker, html)]
    items: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()
    for idx, start in enumerate(indices[:40]):
        end = indices[idx + 1] if idx + 1 < len(indices) else min(len(html), start + 6000)
        block = html[start:end]
        match = re.search(r'<a href="(https?://[^"]+)"[^>]*>(.*?)</a>', block, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        url = match.group(1).strip()
        title = _clean_text(match.group(2))
        if len(title) < 5 or "新浪" in title and len(title) < 8:
            continue
        snippet_match = re.search(r'<p class="content">(.*?)</p>', block, flags=re.IGNORECASE | re.DOTALL)
        snippet = _clean_text(snippet_match.group(1) if snippet_match else title)
        published_dt = _extract_datetime_from_text(block)
        items.append(
            {
                "source": source,
                "url": url,
                "title": title,
                "snippet": snippet,
                "published_at": (published_dt.isoformat() if published_dt else now),
            }
        )
    return items


def _extract_eastmoney_candidates(payload: str, source: str) -> list[dict]:
    obj = _parse_jsonp(payload)
    rows = ((obj.get("result") or {}).get("cmsArticleWebOld") or []) if isinstance(obj, dict) else []
    items: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()
    for row in rows:
        if not isinstance(row, dict):
            continue
        url = _normalize_url(str(row.get("url") or ""), source)
        title = _clean_text(str(row.get("title") or ""))
        if not url or len(title) < 5:
            continue
        snippet = _clean_text(str(row.get("content") or title))
        published_dt = _parse_published_at(str(row.get("date") or ""))
        items.append(
            {
                "source": source,
                "url": url,
                "title": title,
                "snippet": snippet,
                "published_at": published_dt.isoformat() if published_dt else now,
            }
        )
    return items


def _extract_qq_candidates(payload: str, source: str) -> list[dict]:
    try:
        obj = json.loads(payload)
    except json.JSONDecodeError:
        return _extract_generic_html_candidates(payload, source)
    raw_candidates = _collect_link_items(obj)
    items: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()
    for row in raw_candidates[:40]:
        url = _normalize_url(str(row.get("url") or ""), source)
        title = _clean_text(
            str(row.get("title") or row.get("newsTitle") or row.get("name") or row.get("text") or "")
        )
        if not url or len(title) < 5:
            continue
        snippet = _clean_text(str(row.get("summary") or row.get("desc") or row.get("content") or title))
        published_dt = _parse_published_at(
            str(row.get("date") or row.get("time") or row.get("publishTime") or row.get("pubTime") or "")
        )
        items.append(
            {
                "source": source,
                "url": url,
                "title": title,
                "snippet": snippet,
                "published_at": published_dt.isoformat() if published_dt else now,
            }
        )
    return items


def _extract_generic_html_candidates(html: str, source: str) -> list[dict]:
    links = re.findall(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', html, flags=re.IGNORECASE | re.DOTALL)
    now = datetime.now(timezone.utc).isoformat()
    items: list[dict] = []
    for url, title in links[:40]:
        text = _clean_text(title)
        if len(text) < 5:
            continue
        items.append(
            {
                "source": source,
                "url": _normalize_url(url, source),
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


def _build_queries(symbol: str, name: str) -> list[str]:
    seen: set[str] = set()
    queries: list[str] = []
    for query in [symbol, name]:
        normalized = (query or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        queries.append(normalized)
    return queries


def _normalize_item(item: dict, source: str, symbol: str, name: str, cutoff: datetime) -> dict | None:
    title = _clean_text(str(item.get("title") or ""))
    url = _normalize_url(str(item.get("url") or ""), source)
    if len(title) < 5 or not url:
        return None
    snippet = _clean_text(str(item.get("snippet") or title))
    published_dt = _parse_published_at(str(item.get("published_at") or ""))
    if published_dt and published_dt < cutoff:
        return None
    payload = {
        "source": source,
        "url": url,
        "title": title,
        "snippet": snippet,
        "published_at": (published_dt or datetime.now(timezone.utc)).isoformat(),
        "symbol": symbol,
        "name": name,
    }
    if not _is_relevant(payload, symbol, name):
        return None
    payload["sentiment_hint"] = _sentiment_hint(f"{title} {snippet}")
    return payload


def _clean_text(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_url(url: str, source: str) -> str:
    normalized = url.strip()
    if not normalized:
        return ""
    if normalized.startswith("//"):
        return f"https:{normalized}"
    if normalized.startswith("/"):
        return f"{source.rstrip('/')}{normalized}"
    return normalized


def _parse_jsonp(payload: str) -> dict:
    text = payload.strip()
    match = re.match(r"^[^(]+\((.*)\)\s*;?\s*$", text, flags=re.DOTALL)
    if match:
        text = match.group(1).strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return obj if isinstance(obj, dict) else {}


def _collect_link_items(node: Any, depth: int = 0, cap: int = 200) -> list[dict]:
    if depth > 6 or cap <= 0:
        return []
    result: list[dict] = []
    if isinstance(node, dict):
        if isinstance(node.get("url"), str):
            result.append(node)
        for value in node.values():
            if len(result) >= cap:
                break
            result.extend(_collect_link_items(value, depth + 1, cap - len(result)))
        return result
    if isinstance(node, list):
        for value in node:
            if len(result) >= cap:
                break
            result.extend(_collect_link_items(value, depth + 1, cap - len(result)))
    return result


def _extract_datetime_from_text(text: str) -> datetime | None:
    patterns = [
        r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})",
        r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})",
        r"(\d{4}年\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{1,2}(?::\d{1,2})?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        parsed = _parse_published_at(match.group(1))
        if parsed:
            return parsed
    return None


def _parse_published_at(raw: str) -> datetime | None:
    text = _clean_text(raw)
    if not text:
        return None
    iso_text = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(iso_text)
    except ValueError:
        parsed = None
    if parsed is not None:
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    chinese_match = re.search(
        r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?",
        text,
    )
    if chinese_match:
        year, month, day, hour, minute, second = chinese_match.groups()
        parsed = datetime(
            int(year),
            int(month),
            int(day),
            int(hour),
            int(minute),
            int(second or 0),
            tzinfo=timezone.utc,
        )
        return parsed

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            parsed = datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            continue
    return None
