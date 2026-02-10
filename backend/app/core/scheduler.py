from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.db.database import get_db
from app.engine.recommendation_engine import RecommendationEngine


def start_scheduler(engine: RecommendationEngine) -> AsyncIOScheduler | None:
    if not settings.scheduler_enabled:
        return None
    scheduler = AsyncIOScheduler()

    async def _scan_job() -> None:
        with get_db() as db:
            await engine.scan_all_clients(db)

    scheduler.add_job(_scan_job, IntervalTrigger(minutes=settings.scan_interval_minutes), max_instances=1)
    scheduler.start()
    return scheduler
