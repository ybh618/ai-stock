from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db import repository
from app.db.database import get_db
from app.engine.features import extract_market_features
from app.engine.guardrails import (
    apply_guardrails,
    has_enough_evidence,
    is_cooldown_hit,
    is_reversal_allowed,
)
from app.engine.llm_client import LlmClient
from app.engine.prefilter import prefilter_candidate
from app.models.schemas import CandidateContext, LlmOutput
from app.providers.market import MarketDataProvider
from app.providers.news import NewsProvider


@dataclass(slots=True)
class Candidate:
    symbol: str
    name: str
    score: float
    action_hint: str
    reasons: list[str]
    market: dict
    news_items: list[dict]


class RecommendationEngine:
    def __init__(
        self,
        market_provider: MarketDataProvider,
        news_provider: NewsProvider,
        llm_client: LlmClient,
        ws_manager,
    ) -> None:
        self.market_provider = market_provider
        self.news_provider = news_provider
        self.llm_client = llm_client
        self.ws_manager = ws_manager

    async def scan_all_clients(self, db: Session) -> None:
        client_ids = repository.get_all_client_ids(db)
        for client_id in client_ids:
            await self.scan_one_client(db, client_id)

    async def scan_one_client(self, db: Session, client_id: str) -> None:
        watchlist = repository.get_watchlist(db, client_id)
        if not watchlist:
            return
        pref = repository.get_preferences(db, client_id)
        risk_profile = pref.risk_profile if pref else "neutral"
        locale = pref.locale if pref else "zh"
        candidates = await self._collect_candidates(watchlist, risk_profile)
        if not candidates:
            return
        tasks = [
            self._process_candidate(
                client_id=client_id,
                risk_profile=risk_profile,
                locale=locale,
                candidate=candidate,
            )
            for candidate in candidates
        ]
        await asyncio.gather(*tasks)

    async def _collect_candidates(self, watchlist: list, risk_profile: str) -> list[Candidate]:
        candidates: list[Candidate] = []
        for item in watchlist:
            bars_15m = self.market_provider.get_15m_bars(item.symbol)
            bars_daily = self.market_provider.get_daily_bars(item.symbol)
            news = await self.news_provider.get_recent_news(item.symbol, item.name, hours=24)
            market = extract_market_features(item.symbol, bars_15m, bars_daily)
            result = prefilter_candidate(
                symbol=item.symbol,
                name=item.name,
                market=market,
                bars_15m=bars_15m,
                bars_daily=bars_daily,
                news_items=news,
                risk_profile=risk_profile,
            )
            if result.triggered:
                candidates.append(
                    Candidate(
                        symbol=item.symbol,
                        name=item.name,
                        score=result.score,
                        action_hint=result.action_hint,
                        reasons=result.reasons,
                        market=market,
                        news_items=news,
                    )
                )
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates

    async def _process_candidate(
        self,
        client_id: str,
        risk_profile: str,
        locale: str,
        candidate: Candidate,
    ) -> None:
        with get_db() as db:
            last_rec = repository.get_last_recommendation(db, client_id, candidate.symbol)
        if last_rec and is_cooldown_hit(
            {"symbol": last_rec.symbol, "action": last_rec.action, "created_at": last_rec.created_at},
            candidate.symbol,
            candidate.action_hint,
        ):
            return

        context = CandidateContext(
            client_id=client_id,
            symbol=candidate.symbol,
            name=candidate.name,
            risk_profile=risk_profile,
            locale=locale,
            market_features=candidate.market.get("features", []),
            news_items=candidate.news_items[:8],
            recent_recommendations=(
                [
                    {
                        "action": last_rec.action,
                        "target_position_pct": last_rec.target_position_pct,
                        "created_at": last_rec.created_at.isoformat(),
                        "confidence": last_rec.confidence,
                    }
                ]
                if last_rec
                else []
            ),
        )
        llm_output = await self.llm_client.generate(context)
        recommendation = self._finalize_recommendation(
            output=llm_output,
            action_hint=candidate.action_hint,
            market_features=context.market_features,
            news_items=context.news_items,
        )
        recommendation = apply_guardrails(recommendation, risk_profile)
        if not has_enough_evidence(recommendation):
            return
        if not is_reversal_allowed(
            {"action": last_rec.action} if last_rec else None,
            recommendation.action,
            recommendation.confidence,
        ):
            return
        with get_db() as db:
            rec_row = repository.create_recommendation(
                db,
                client_id=client_id,
                symbol=candidate.symbol,
                action=recommendation.action,
                target_position_pct=recommendation.target_position_pct,
                summary_zh=recommendation.summary_zh,
                summary_en=recommendation.summary_en,
                risk=recommendation.risk,
                evidence=recommendation.evidence,
                confidence=recommendation.confidence,
                cooldown_key=f"{candidate.symbol}:{recommendation.action}",
            )
        if await self.ws_manager.is_online(client_id):
            await self.ws_manager.send_event(
                client_id,
                "server.recommendation.created",
                {
                    "recommendation": {
                        "id": rec_row.id,
                        "client_id": rec_row.client_id,
                        "symbol": rec_row.symbol,
                        "created_at": rec_row.created_at.isoformat(),
                        "action": rec_row.action,
                        "target_position_pct": rec_row.target_position_pct,
                        "summary_zh": rec_row.summary_zh,
                        "summary_en": rec_row.summary_en,
                        "risk": rec_row.risk,
                        "evidence": rec_row.evidence,
                        "confidence": rec_row.confidence,
                        "cooldown_key": rec_row.cooldown_key,
                    }
                },
            )

    def _finalize_recommendation(
        self, output: LlmOutput, action_hint: str, market_features: list[dict], news_items: list[dict]
    ) -> LlmOutput:
        action = output.action if output.action in {"buy", "sell", "hold"} else action_hint
        evidence = output.evidence or {}
        evidence.setdefault("market_features", market_features[:4])
        evidence.setdefault("news_citations", news_items[:4])
        risk = output.risk or {}
        risk.setdefault("invalidate_conditions", ["signal_invalidated"])
        return LlmOutput(
            summary_zh=output.summary_zh or "信号已触发，请结合风险偏好判断。",
            summary_en=output.summary_en or "Signal triggered. Evaluate with your risk profile.",
            action=action,
            target_position_pct=output.target_position_pct,
            risk=risk,
            evidence=evidence,
            confidence=output.confidence,
        )
