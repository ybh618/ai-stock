from __future__ import annotations

import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request

from app.core.config import settings
from app.db.database import get_db
from app.db.repository import create_feedback, get_recommendations, get_watchlist
from app.models.schemas import (
    FeedbackInput,
    NewsItemDTO,
    NewsListResponse,
    RecommendationListResponse,
    RecommendationTriggerInput,
    RecommendationTriggerResponse,
)

router = APIRouter(prefix="/v1", tags=["api"])


@router.get("/recommendations", response_model=RecommendationListResponse)
def list_recommendations(
    client_id: str = Query(...),
    limit: int = Query(50, ge=1, le=500),
    before: datetime | None = Query(None),
):
    with get_db() as db:
        items = get_recommendations(db, client_id=client_id, limit=limit, before=before)
        return RecommendationListResponse(items=items)


@router.get("/news", response_model=NewsListResponse)
async def list_latest_news(
    request: Request,
    client_id: str = Query(...),
    hours: int = Query(24, ge=1, le=168),
    per_symbol_limit: int = Query(5, ge=1, le=20),
    limit: int = Query(50, ge=1, le=200),
):
    news_provider = getattr(request.app.state, "news_provider", None)
    if news_provider is None:
        raise HTTPException(status_code=500, detail="news provider unavailable")
    with get_db() as db:
        watchlist = get_watchlist(db, client_id)
    if not watchlist:
        return NewsListResponse(items=[])

    tasks = [news_provider.get_recent_news(item.symbol, item.name, hours=hours) for item in watchlist]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    merged: list[dict] = []
    seen: set[str] = set()
    for symbol_news in results:
        if isinstance(symbol_news, Exception):
            continue
        for item in symbol_news[:per_symbol_limit]:
            key = f"{item.get('symbol', '')}:{item.get('url', '')}:{item.get('title', '')}"
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
    merged.sort(key=lambda x: str(x.get("published_at", "")), reverse=True)
    return NewsListResponse(items=[NewsItemDTO.model_validate(item) for item in merged[:limit]])


@router.post("/recommendations/trigger", response_model=RecommendationTriggerResponse)
async def trigger_recommendations(request: Request, payload: RecommendationTriggerInput):
    rec_engine = getattr(request.app.state, "rec_engine", None)
    if rec_engine is None:
        raise HTTPException(status_code=500, detail="recommendation engine unavailable")
    with get_db() as db:
        await rec_engine.scan_one_client(db, payload.client_id)
    return RecommendationTriggerResponse(client_id=payload.client_id)


@router.post("/feedback")
def submit_feedback(payload: FeedbackInput):
    with get_db() as db:
        row = create_feedback(db, payload)
        if row is None:
            raise HTTPException(status_code=400, detail="Unable to store feedback")
        return {"ok": True, "id": row.id}


@router.get("/config")
def get_config():
    return {
        "scan_interval_minutes": settings.scan_interval_minutes,
        "cooldown_minutes": settings.cooldown_minutes,
        "evidence_min_items": settings.evidence_min_items,
        "max_position_pct": {
            "aggressive": settings.max_position_aggressive,
            "neutral": settings.max_position_neutral,
            "conservative": settings.max_position_conservative,
        },
        "llm_concurrency": settings.llm_max_concurrency,
    }


@router.post("/debug/run")
async def run_debug_checks(
    request: Request,
    client_id: str | None = Query(default=None),
):
    debug_service = getattr(request.app.state, "debug_service", None)
    if debug_service is None:
        raise HTTPException(status_code=500, detail="debug service unavailable")
    return await debug_service.run_checks(client_id=client_id)


@router.get("/debug/status")
async def debug_status(request: Request):
    ws_manager = getattr(request.app.state, "ws_manager", None)
    if ws_manager is None:
        raise HTTPException(status_code=500, detail="ws manager unavailable")
    online_clients = await ws_manager.online_clients_count()
    return {
        "online_clients": online_clients,
        "scheduler_enabled": settings.scheduler_enabled,
        "scan_interval_minutes": settings.scan_interval_minutes,
    }
