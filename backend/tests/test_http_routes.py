from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.http_routes import router


class _WatchItem:
    def __init__(self, symbol: str, name: str) -> None:
        self.symbol = symbol
        self.name = name


class _StubNewsProvider:
    async def get_recent_news(self, symbol: str, name: str, hours: int = 24) -> list[dict]:
        return [
            {
                "source": "stub",
                "url": f"https://example.com/{symbol}/1",
                "title": f"{name} 利好消息",
                "snippet": "公司披露新订单",
                "published_at": "2026-02-10T10:00:00+00:00",
                "symbol": symbol,
                "name": name,
                "sentiment_hint": "positive",
            }
        ]


class _StubRecommendationEngine:
    def __init__(self) -> None:
        self.last_client_id: str | None = None

    async def scan_one_client(self, db, client_id: str) -> None:  # noqa: ANN001
        self.last_client_id = client_id


def _build_test_app(rec_engine: _StubRecommendationEngine | None = None) -> FastAPI:
    app = FastAPI()
    app.state.news_provider = _StubNewsProvider()
    app.state.rec_engine = rec_engine or _StubRecommendationEngine()
    app.include_router(router)
    return app


def test_news_endpoint_returns_news_items(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.http_routes.get_watchlist",
        lambda db, client_id: [_WatchItem("600519", "贵州茅台")],  # noqa: ARG005
    )

    app = _build_test_app()
    with TestClient(app) as client:
        response = client.get("/v1/news", params={"client_id": "client-a"})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["symbol"] == "600519"
    assert payload["items"][0]["source"] == "stub"


def test_trigger_endpoint_runs_scan_for_client(monkeypatch) -> None:
    monkeypatch.setattr("app.api.http_routes.get_watchlist", lambda db, client_id: [])  # noqa: ARG005

    rec_engine = _StubRecommendationEngine()
    app = _build_test_app(rec_engine=rec_engine)
    with TestClient(app) as client:
        response = client.post("/v1/recommendations/trigger", json={"client_id": "client-b"})
    assert response.status_code == 200
    assert response.json() == {"ok": True, "client_id": "client-b"}
    assert rec_engine.last_client_id == "client-b"
