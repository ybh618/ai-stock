from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WatchlistItemInput(BaseModel):
    symbol: str
    name: str
    group: str = "default"
    sort_index: int = 0


class PreferencesInput(BaseModel):
    locale: str = "zh"
    notifications_enabled: bool = True
    quiet_hours: dict = Field(default_factory=dict)
    risk_profile: str = "neutral"


class ClientHelloPayload(BaseModel):
    client_id: str
    app_version: str = "0.1.0"
    locale: str = "zh"


class SyncStatePayload(BaseModel):
    client_id: str
    watchlist: list[WatchlistItemInput]
    preferences: PreferencesInput


class WsEnvelope(BaseModel):
    type: str
    payload: dict = Field(default_factory=dict)


class FeedbackInput(BaseModel):
    client_id: str
    recommendation_id: int
    helpful: bool
    reason: str | None = None


class RecommendationDTO(BaseModel):
    id: int
    client_id: str
    symbol: str
    created_at: datetime
    action: str
    target_position_pct: float
    summary_zh: str
    summary_en: str
    risk: dict
    evidence: dict
    confidence: float
    cooldown_key: str

    model_config = ConfigDict(from_attributes=True)


class RecommendationListResponse(BaseModel):
    items: list[RecommendationDTO]


class NewsItemDTO(BaseModel):
    source: str
    url: str
    title: str
    snippet: str
    published_at: str
    symbol: str
    name: str
    sentiment_hint: str = "neutral"


class NewsListResponse(BaseModel):
    items: list[NewsItemDTO]


class RecommendationTriggerInput(BaseModel):
    client_id: str


class RecommendationTriggerResponse(BaseModel):
    ok: bool = True
    client_id: str
    state: str = "started"
    message: str = ""


class RecommendationStatusResponse(BaseModel):
    client_id: str
    state: str = "idle"
    step: str = "idle"
    progress: int = 0
    message: str = ""
    total_watchlist: int = 0
    total_candidates: int = 0
    processed_candidates: int = 0
    created_recommendations: int = 0
    started_at: str | None = None
    updated_at: str | None = None
    finished_at: str | None = None
    error: str | None = None


class DiscoverStockDTO(BaseModel):
    symbol: str
    name: str
    action: str
    score: float = 0.0
    confidence: float = 0.0
    summary_zh: str
    summary_en: str
    reasons: list[str] = Field(default_factory=list)
    news_count: int = 0
    target_position_pct: float = 0.0


class DiscoverStockListResponse(BaseModel):
    items: list[DiscoverStockDTO]


class DiscoverStockTriggerInput(BaseModel):
    client_id: str
    limit: int = 6
    universe_limit: int = 50


class DiscoverStockTriggerResponse(BaseModel):
    ok: bool = True
    client_id: str
    state: str = "started"
    message: str = ""


class DiscoverStockStatusResponse(BaseModel):
    client_id: str
    state: str = "idle"
    step: str = "idle"
    progress: int = 0
    message: str = ""
    limit: int = 0
    universe_limit: int = 0
    scanned_candidates: int = 0
    total_candidates: int = 0
    started_at: str | None = None
    updated_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    items: list[DiscoverStockDTO] = Field(default_factory=list)


class LlmOutput(BaseModel):
    summary_zh: str
    summary_en: str
    action: str
    target_position_pct: float
    risk: dict = Field(default_factory=dict)
    evidence: dict = Field(default_factory=dict)
    confidence: float = 0.0


class CandidateContext(BaseModel):
    client_id: str
    symbol: str
    name: str
    risk_profile: str
    locale: str
    market_features: list[dict]
    news_items: list[dict]
    recent_recommendations: list[dict]
