from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.models.orm import (
    ClientPreferenceORM,
    FeedbackORM,
    RecommendationORM,
    WatchlistItemORM,
)
from app.models.schemas import FeedbackInput, PreferencesInput, WatchlistItemInput


def get_all_client_ids(db: Session) -> list[str]:
    rows = db.execute(select(ClientPreferenceORM.client_id)).all()
    pref_clients = {item[0] for item in rows}
    watch_rows = db.execute(select(WatchlistItemORM.client_id)).all()
    watch_clients = {item[0] for item in watch_rows}
    return sorted(pref_clients.union(watch_clients))


def replace_watchlist(db: Session, client_id: str, items: list[WatchlistItemInput]) -> None:
    db.execute(delete(WatchlistItemORM).where(WatchlistItemORM.client_id == client_id))
    for item in items:
        db.add(
            WatchlistItemORM(
                client_id=client_id,
                symbol=item.symbol,
                name=item.name,
                group_name=item.group,
                sort_index=item.sort_index,
            )
        )
    db.commit()


def upsert_preferences(db: Session, client_id: str, preferences: PreferencesInput) -> None:
    row = db.scalar(select(ClientPreferenceORM).where(ClientPreferenceORM.client_id == client_id))
    if row is None:
        row = ClientPreferenceORM(
            client_id=client_id,
            locale=preferences.locale,
            notifications_enabled=preferences.notifications_enabled,
            quiet_hours=preferences.quiet_hours,
            risk_profile=preferences.risk_profile,
        )
        db.add(row)
    else:
        row.locale = preferences.locale
        row.notifications_enabled = preferences.notifications_enabled
        row.quiet_hours = preferences.quiet_hours
        row.risk_profile = preferences.risk_profile
        row.updated_at = datetime.utcnow()
    db.commit()


def get_watchlist(db: Session, client_id: str) -> list[WatchlistItemORM]:
    rows = db.execute(
        select(WatchlistItemORM)
        .where(WatchlistItemORM.client_id == client_id)
        .order_by(WatchlistItemORM.group_name, WatchlistItemORM.sort_index)
    ).scalars()
    return list(rows)


def get_preferences(db: Session, client_id: str) -> ClientPreferenceORM | None:
    return db.scalar(select(ClientPreferenceORM).where(ClientPreferenceORM.client_id == client_id))


def create_recommendation(
    db: Session,
    *,
    client_id: str,
    symbol: str,
    action: str,
    target_position_pct: float,
    summary_zh: str,
    summary_en: str,
    risk: dict,
    evidence: dict,
    confidence: float,
    cooldown_key: str,
) -> RecommendationORM:
    row = RecommendationORM(
        client_id=client_id,
        symbol=symbol,
        action=action,
        target_position_pct=target_position_pct,
        summary_zh=summary_zh,
        summary_en=summary_en,
        risk=risk,
        evidence=evidence,
        confidence=confidence,
        cooldown_key=cooldown_key,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_recommendations(
    db: Session, client_id: str, limit: int = 100, before: datetime | None = None
) -> list[RecommendationORM]:
    query = select(RecommendationORM).where(RecommendationORM.client_id == client_id)
    if before is not None:
        query = query.where(RecommendationORM.created_at < before)
    query = query.order_by(desc(RecommendationORM.created_at)).limit(limit)
    return list(db.execute(query).scalars())


def get_last_recommendation(db: Session, client_id: str, symbol: str) -> RecommendationORM | None:
    query = (
        select(RecommendationORM)
        .where(RecommendationORM.client_id == client_id, RecommendationORM.symbol == symbol)
        .order_by(desc(RecommendationORM.created_at))
        .limit(1)
    )
    return db.scalar(query)


def create_feedback(db: Session, payload: FeedbackInput) -> FeedbackORM:
    row = FeedbackORM(
        client_id=payload.client_id,
        recommendation_id=payload.recommendation_id,
        helpful=payload.helpful,
        reason=payload.reason,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
