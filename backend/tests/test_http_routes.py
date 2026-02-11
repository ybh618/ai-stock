from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.http_routes import router


class _WatchItem:
    def __init__(self, symbol: str, name: str) -> None:
        self.symbol = symbol
        self.name = name


class _StubNewsProvider:
    async def get_recent_news(
        self, symbol: str, name: str, hours: int = 24
    ) -> list[dict]:
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
        self._status: dict[str, dict] = {}
        self._discover_status: dict[str, dict] = {}

    async def scan_one_client(self, db, client_id: str) -> None:  # noqa: ANN001
        self.last_client_id = client_id

    async def trigger_scan(self, client_id: str) -> tuple[bool, str, str]:
        self.last_client_id = client_id
        self._status[client_id] = {
            "client_id": client_id,
            "state": "running",
            "step": "collecting_candidates",
            "progress": 30,
            "message": "Collecting market/news data.",
            "total_watchlist": 5,
            "total_candidates": 0,
            "processed_candidates": 0,
            "created_recommendations": 0,
            "started_at": "2026-02-11T00:00:00+00:00",
            "updated_at": "2026-02-11T00:00:10+00:00",
            "finished_at": None,
            "error": None,
        }
        return True, "started", "AI selection started."

    async def get_scan_status(self, client_id: str) -> dict:
        return self._status.get(
            client_id,
            {
                "client_id": client_id,
                "state": "idle",
                "step": "idle",
                "progress": 0,
                "message": "",
                "total_watchlist": 0,
                "total_candidates": 0,
                "processed_candidates": 0,
                "created_recommendations": 0,
                "started_at": None,
                "updated_at": None,
                "finished_at": None,
                "error": None,
            },
        )

    async def discover_stocks(
        self,
        client_id: str,
        limit: int = 5,
        universe_limit: int = 80,
    ) -> list[dict]:
        _ = (client_id, limit, universe_limit)
        return [
            {
                "symbol": "600519",
                "name": "贵州茅台",
                "action": "buy",
                "score": 2.5,
                "confidence": 0.72,
                "summary_zh": "量价与新闻共振，值得关注。",
                "summary_en": "Volume-price and news resonance, worth tracking.",
                "reasons": ["buy_breakout", "buy_event"],
                "news_count": 3,
                "target_position_pct": 15.0,
            }
        ]

    async def trigger_discovery(
        self,
        client_id: str,
        limit: int = 6,
        universe_limit: int = 50,
    ) -> tuple[bool, str, str]:
        self.last_client_id = client_id
        self._discover_status[client_id] = {
            "client_id": client_id,
            "state": "running",
            "step": "collecting_candidates",
            "progress": 35,
            "message": "Collecting market/news data (12/40).",
            "limit": limit,
            "universe_limit": universe_limit,
            "scanned_candidates": 12,
            "total_candidates": 40,
            "started_at": "2026-02-11T00:00:00+00:00",
            "updated_at": "2026-02-11T00:00:10+00:00",
            "finished_at": None,
            "error": None,
            "items": [],
        }
        return True, "started", "Discovery task started."

    async def get_discovery_status(self, client_id: str) -> dict:
        return self._discover_status.get(
            client_id,
            {
                "client_id": client_id,
                "state": "idle",
                "step": "idle",
                "progress": 0,
                "message": "",
                "limit": 0,
                "universe_limit": 0,
                "scanned_candidates": 0,
                "total_candidates": 0,
                "started_at": None,
                "updated_at": None,
                "finished_at": None,
                "error": None,
                "items": [],
            },
        )


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
        response = client.post(
            "/v1/recommendations/trigger", json={"client_id": "client-b"}
        )
    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "client_id": "client-b",
        "state": "started",
        "message": "AI selection started.",
    }
    assert rec_engine.last_client_id == "client-b"


def test_recommendation_status_endpoint_returns_progress() -> None:
    rec_engine = _StubRecommendationEngine()
    app = _build_test_app(rec_engine=rec_engine)
    with TestClient(app) as client:
        client.post("/v1/recommendations/trigger", json={"client_id": "client-c"})
        response = client.get(
            "/v1/recommendations/status", params={"client_id": "client-c"}
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["client_id"] == "client-c"
    assert payload["state"] == "running"
    assert payload["step"] == "collecting_candidates"


def test_discover_stocks_endpoint_returns_items() -> None:
    rec_engine = _StubRecommendationEngine()
    app = _build_test_app(rec_engine=rec_engine)
    with TestClient(app) as client:
        response = client.get(
            "/v1/discover/stocks",
            params={"client_id": "client-d", "limit": 3, "universe_limit": 60},
        )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["symbol"] == "600519"


def test_discover_trigger_and_status_endpoints() -> None:
    rec_engine = _StubRecommendationEngine()
    app = _build_test_app(rec_engine=rec_engine)
    with TestClient(app) as client:
        trigger_response = client.post(
            "/v1/discover/stocks/trigger",
            json={"client_id": "client-e", "limit": 4, "universe_limit": 60},
        )
        status_response = client.get(
            "/v1/discover/stocks/status",
            params={"client_id": "client-e"},
        )
    assert trigger_response.status_code == 200
    assert trigger_response.json() == {
        "ok": True,
        "client_id": "client-e",
        "state": "started",
        "message": "Discovery task started.",
    }
    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["client_id"] == "client-e"
    assert payload["state"] == "running"
    assert payload["progress"] == 35
