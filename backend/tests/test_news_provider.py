from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from app.providers.news import (
    ScrapingNewsProvider,
    _NewsSource,
    _dedupe_news,
    _extract_eastmoney_candidates,
    _extract_sina_candidates,
    _parse_published_at,
    _sentiment_hint,
)


def test_extract_sina_candidates_parses_core_fields() -> None:
    html = """
    <div class="box-result clearfix" data-sudaclick="blk_result_index_0">
      <div class="r-info r-info2">
        <h2><a href="https://finance.sina.com.cn/stock/bxjj/2026-02-03/doc-test.shtml" target="_blank">
          贵州茅台(600519.SH)：已累计回购5.71亿元股份
        </a></h2>
        <p class="content">贵州茅台(600519.SH)公布，累计回购股份。</p>
        <h2><span class="fgray_time">2026-02-03 18:11:21</span></h2>
      </div>
    </div>
    """
    items = _extract_sina_candidates(html, "https://finance.sina.com.cn")
    assert len(items) == 1
    assert items[0]["url"].startswith("https://finance.sina.com.cn/stock/")
    assert "贵州茅台" in items[0]["title"]
    assert "累计回购" in items[0]["snippet"]
    assert items[0]["published_at"].startswith("2026-02-03T18:11:21")


def test_extract_eastmoney_candidates_parses_jsonp_payload() -> None:
    payload = (
        'jQuery_news({"result":{"cmsArticleWebOld":[{"date":"2026-02-10 16:58:22",'
        '"title":"食品饮料行业资金流出榜：贵州茅台、五粮液等净流出资金居前",'
        '"content":"食品饮料行业今日下跌，主力资金净流出。",'
        '"url":"https://finance.eastmoney.com/a/202602103646721421.html"}]}})'
    )
    items = _extract_eastmoney_candidates(payload, "https://finance.eastmoney.com")
    assert len(items) == 1
    assert items[0]["url"].startswith("https://finance.eastmoney.com/a/")
    assert "贵州茅台" in items[0]["title"]
    assert items[0]["published_at"].startswith("2026-02-10T16:58:22")


def test_parse_published_at_supports_chinese_datetime() -> None:
    parsed = _parse_published_at("2026年2月3日 18:11")
    assert parsed is not None
    assert parsed.year == 2026
    assert parsed.month == 2
    assert parsed.day == 3
    assert parsed.hour == 18
    assert parsed.minute == 11


def test_get_recent_news_filters_cutoff_and_relevance() -> None:
    class StubProvider(ScrapingNewsProvider):
        async def _fetch_from_source(self, client, source, query):  # type: ignore[override]
            now = datetime.now(timezone.utc)
            return [
                {
                    "url": "https://example.com/relevant",
                    "title": "贵州茅台宣布回购计划 600519",
                    "snippet": "回购方案发布，市场关注度提升",
                    "published_at": now.isoformat(),
                },
                {
                    "url": "https://example.com/stale",
                    "title": "贵州茅台旧闻 600519",
                    "snippet": "时间过旧",
                    "published_at": (now - timedelta(days=3)).isoformat(),
                },
                {
                    "url": "https://example.com/unrelated",
                    "title": "其他公司公告",
                    "snippet": "与目标股票无关",
                    "published_at": now.isoformat(),
                },
            ]

    provider = StubProvider(timeout_seconds=1.0)
    provider.sources = [_NewsSource(name="stub", base_url="https://finance.sina.com.cn", kind="stub")]

    items = asyncio.run(provider.get_recent_news(symbol="600519", name="贵州茅台", hours=24))
    assert len(items) == 1
    assert items[0]["url"] == "https://example.com/relevant"
    assert items[0]["sentiment_hint"] == "positive"


def test_sentiment_and_dedupe_helpers() -> None:
    assert _sentiment_hint("公司公告增持并签署新订单") == "positive"
    assert _sentiment_hint("公司被立案处罚") == "negative"
    assert _sentiment_hint("中性内容") == "neutral"

    deduped = _dedupe_news(
        [
            {"source": "a", "title": "t1"},
            {"source": "a", "title": "t1"},
            {"source": "b", "title": "t1"},
        ]
    )
    assert len(deduped) == 2
