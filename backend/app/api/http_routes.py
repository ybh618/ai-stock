from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request

from app.core.config import settings
from app.db.database import get_db
from app.db.repository import create_feedback, get_recommendations
from app.models.schemas import FeedbackInput, RecommendationListResponse

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
