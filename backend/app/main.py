from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.http_routes import router as http_router
from app.api.ws_routes import build_ws_router
from app.core.config import settings
from app.core.debug_service import DebugService
from app.core.scheduler import start_scheduler
from app.core.websocket_manager import WebSocketManager
from app.db.database import Base, engine
from app.engine.llm_client import LlmClient
from app.engine.recommendation_engine import RecommendationEngine
from app.providers.market import AkShareMarketDataProvider
from app.providers.news import ScrapingNewsProvider

ws_manager = WebSocketManager()
market_provider = AkShareMarketDataProvider()
news_provider = ScrapingNewsProvider()
llm_client = LlmClient()
rec_engine = RecommendationEngine(
    market_provider=market_provider,
    news_provider=news_provider,
    llm_client=llm_client,
    ws_manager=ws_manager,
)
debug_service = DebugService(
    market_provider=market_provider,
    news_provider=news_provider,
    ws_manager=ws_manager,
)
_scheduler = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _scheduler
    Base.metadata.create_all(bind=engine)
    _scheduler = start_scheduler(rec_engine)
    yield
    if _scheduler:
        _scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.state.debug_service = debug_service
app.state.ws_manager = ws_manager
app.state.news_provider = news_provider
app.state.rec_engine = rec_engine
app.include_router(http_router)
app.include_router(build_ws_router(ws_manager))


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
