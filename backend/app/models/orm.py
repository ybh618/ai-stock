from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class WatchlistItemORM(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("client_id", "symbol", name="uq_watchlist_client_symbol"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(128))
    group_name: Mapped[str] = mapped_column(String(64), default="default")
    sort_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ClientPreferenceORM(Base):
    __tablename__ = "client_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    locale: Mapped[str] = mapped_column(String(8), default="zh")
    notifications_enabled: Mapped[bool] = mapped_column(default=True)
    quiet_hours: Mapped[dict] = mapped_column(JSON, default=dict)
    risk_profile: Mapped[str] = mapped_column(String(16), default="neutral")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RecommendationORM(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    action: Mapped[str] = mapped_column(String(16))
    target_position_pct: Mapped[float] = mapped_column(Float)
    summary_zh: Mapped[str] = mapped_column(Text)
    summary_en: Mapped[str] = mapped_column(Text)
    risk: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    cooldown_key: Mapped[str] = mapped_column(String(128), index=True)


class FeedbackORM(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    recommendation_id: Mapped[int] = mapped_column(Integer, index=True)
    helpful: Mapped[bool] = mapped_column(default=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
