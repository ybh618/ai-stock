from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

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


@dataclass(slots=True)
class ScanStatus:
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
        self._status_lock = asyncio.Lock()
        self._status_by_client: dict[str, ScanStatus] = {}
        self._manual_tasks: dict[str, asyncio.Task] = {}

    async def trigger_scan(self, client_id: str) -> tuple[bool, str, str]:
        async with self._status_lock:
            existing = self._manual_tasks.get(client_id)
            if existing and not existing.done():
                current = self._status_by_client.get(client_id)
                message = current.message if current else "AI selection is running."
                return True, "already_running", message
            task = asyncio.create_task(self._run_manual_scan(client_id))
            self._manual_tasks[client_id] = task
        return True, "started", "AI selection started."

    async def get_scan_status(self, client_id: str) -> dict:
        async with self._status_lock:
            status = self._status_by_client.get(client_id)
            if status is None:
                return asdict(ScanStatus(client_id=client_id))
            return asdict(status)

    async def _run_manual_scan(self, client_id: str) -> None:
        try:
            with get_db() as db:
                await self.scan_one_client(db, client_id, source="manual")
        except Exception as exc:
            await self._set_failed_status(
                client_id, message="AI selection failed.", error=str(exc)
            )
        finally:
            async with self._status_lock:
                current = self._manual_tasks.get(client_id)
                if current is asyncio.current_task():
                    self._manual_tasks.pop(client_id, None)

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    async def _set_running_status(
        self,
        client_id: str,
        *,
        step: str,
        progress: int,
        message: str,
        total_watchlist: int | None = None,
        total_candidates: int | None = None,
        processed_candidates: int | None = None,
        created_recommendations: int | None = None,
    ) -> None:
        async with self._status_lock:
            now = self._now_iso()
            status = self._status_by_client.get(client_id) or ScanStatus(
                client_id=client_id
            )
            if status.started_at is None:
                status.started_at = now
            status.state = "running"
            status.step = step
            status.progress = max(0, min(99, progress))
            status.message = message
            status.updated_at = now
            status.finished_at = None
            status.error = None
            if total_watchlist is not None:
                status.total_watchlist = total_watchlist
            if total_candidates is not None:
                status.total_candidates = total_candidates
            if processed_candidates is not None:
                status.processed_candidates = processed_candidates
            if created_recommendations is not None:
                status.created_recommendations = created_recommendations
            self._status_by_client[client_id] = status

    async def _set_succeeded_status(self, client_id: str, message: str) -> None:
        async with self._status_lock:
            now = self._now_iso()
            status = self._status_by_client.get(client_id) or ScanStatus(
                client_id=client_id
            )
            if status.started_at is None:
                status.started_at = now
            status.state = "succeeded"
            status.step = "done"
            status.progress = 100
            status.message = message
            status.updated_at = now
            status.finished_at = now
            status.error = None
            self._status_by_client[client_id] = status

    async def _set_failed_status(
        self, client_id: str, message: str, error: str
    ) -> None:
        async with self._status_lock:
            now = self._now_iso()
            status = self._status_by_client.get(client_id) or ScanStatus(
                client_id=client_id
            )
            if status.started_at is None:
                status.started_at = now
            status.state = "failed"
            status.step = "failed"
            status.progress = 100
            status.message = message
            status.updated_at = now
            status.finished_at = now
            status.error = error
            self._status_by_client[client_id] = status

    async def discover_stocks(
        self,
        client_id: str,
        limit: int = 5,
        universe_limit: int = 80,
    ) -> list[dict]:
        with get_db() as db:
            pref = repository.get_preferences(db, client_id)
            fallback_watchlist = repository.get_watchlist(db, client_id)
        risk_profile = pref.risk_profile if pref else "neutral"
        locale = pref.locale if pref else "zh"

        capped_universe = max(20, min(universe_limit, 120))
        raw_candidates: list[dict] = []
        try:
            raw_candidates = await asyncio.wait_for(
                asyncio.to_thread(
                    self.market_provider.discover_candidates,
                    capped_universe,
                ),
                timeout=12,
            )
        except Exception:
            raw_candidates = []
        if not raw_candidates:
            raw_candidates = [
                {"symbol": item.symbol, "name": item.name}
                for item in fallback_watchlist
            ]
        if not raw_candidates:
            return []
        scan_limit = min(len(raw_candidates), max(limit * 6, 30))
        raw_candidates = raw_candidates[:scan_limit]

        semaphore = asyncio.Semaphore(4)
        scored_candidates: list[Candidate] = []
        scored_lock = asyncio.Lock()

        async def _evaluate(item: dict) -> None:
            symbol = str(item.get("symbol") or "").strip()
            name = str(item.get("name") or "").strip() or symbol
            if not symbol:
                return
            async with semaphore:
                try:
                    bars_15m = await asyncio.wait_for(
                        asyncio.to_thread(self.market_provider.get_15m_bars, symbol),
                        timeout=8,
                    )
                    bars_daily = await asyncio.wait_for(
                        asyncio.to_thread(self.market_provider.get_daily_bars, symbol),
                        timeout=8,
                    )
                    news = await asyncio.wait_for(
                        self.news_provider.get_recent_news(symbol, name, hours=24),
                        timeout=10,
                    )
                    market = extract_market_features(symbol, bars_15m, bars_daily)
                    result = prefilter_candidate(
                        symbol=symbol,
                        name=name,
                        market=market,
                        bars_15m=bars_15m,
                        bars_daily=bars_daily,
                        news_items=news,
                        risk_profile=risk_profile,
                    )
                    if not result.triggered:
                        return
                    async with scored_lock:
                        scored_candidates.append(
                            Candidate(
                                symbol=symbol,
                                name=name,
                                score=result.score,
                                action_hint=result.action_hint,
                                reasons=result.reasons,
                                market=market,
                                news_items=news,
                            )
                        )
                except Exception:
                    return

        try:
            await asyncio.wait_for(
                asyncio.gather(
                    *[_evaluate(item) for item in raw_candidates],
                    return_exceptions=True,
                ),
                timeout=35,
            )
        except Exception:
            pass
        scored_candidates.sort(key=lambda c: c.score, reverse=True)
        shortlist = scored_candidates[: max(limit * 2, limit)]
        if not shortlist:
            return []

        output: list[dict] = []
        for candidate in shortlist:
            try:
                context = CandidateContext(
                    client_id=client_id,
                    symbol=candidate.symbol,
                    name=candidate.name,
                    risk_profile=risk_profile,
                    locale=locale,
                    market_features=candidate.market.get("features", []),
                    news_items=candidate.news_items[:8],
                    recent_recommendations=[],
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
                    continue
                output.append(
                    {
                        "symbol": candidate.symbol,
                        "name": candidate.name,
                        "action": recommendation.action,
                        "score": candidate.score,
                        "confidence": recommendation.confidence,
                        "summary_zh": recommendation.summary_zh,
                        "summary_en": recommendation.summary_en,
                        "reasons": candidate.reasons,
                        "news_count": len(candidate.news_items),
                        "target_position_pct": recommendation.target_position_pct,
                    }
                )
            except Exception:
                continue
            if len(output) >= limit:
                break
        return output

    async def scan_all_clients(self, db: Session) -> None:
        client_ids = repository.get_all_client_ids(db)
        for client_id in client_ids:
            await self.scan_one_client(db, client_id, source="scheduler")

    async def scan_one_client(
        self, db: Session, client_id: str, source: str = "scheduler"
    ) -> None:
        try:
            await self._set_running_status(
                client_id,
                step="loading_watchlist",
                progress=5,
                message="Loading watchlist.",
                processed_candidates=0,
                created_recommendations=0,
            )
            watchlist = repository.get_watchlist(db, client_id)
            total_watchlist = len(watchlist)
            if not watchlist:
                await self._set_succeeded_status(client_id, "Watchlist is empty.")
                return
            pref = repository.get_preferences(db, client_id)
            risk_profile = pref.risk_profile if pref else "neutral"
            locale = pref.locale if pref else "zh"
            await self._set_running_status(
                client_id,
                step="collecting_candidates",
                progress=10,
                message=f"Collecting market/news data (0/{total_watchlist}).",
                total_watchlist=total_watchlist,
                processed_candidates=0,
                created_recommendations=0,
            )
            candidates = await self._collect_candidates(
                watchlist=watchlist, risk_profile=risk_profile, client_id=client_id
            )
            if not candidates:
                await self._set_succeeded_status(
                    client_id, "No candidates were triggered."
                )
                return
            total_candidates = len(candidates)
            await self._set_running_status(
                client_id,
                step="llm_reasoning",
                progress=60,
                message=f"Running AI analysis (0/{total_candidates}).",
                total_watchlist=total_watchlist,
                total_candidates=total_candidates,
                processed_candidates=0,
                created_recommendations=0,
            )
            processed = 0
            created = 0
            progress_lock = asyncio.Lock()

            async def _run_candidate(candidate: Candidate) -> None:
                nonlocal processed, created
                created_one = await self._process_candidate(
                    client_id=client_id,
                    risk_profile=risk_profile,
                    locale=locale,
                    candidate=candidate,
                )
                async with progress_lock:
                    processed += 1
                    if created_one:
                        created += 1
                    progress = 60 + int((processed / max(1, total_candidates)) * 35)
                    await self._set_running_status(
                        client_id,
                        step="llm_reasoning",
                        progress=progress,
                        message=f"Running AI analysis ({processed}/{total_candidates}).",
                        total_watchlist=total_watchlist,
                        total_candidates=total_candidates,
                        processed_candidates=processed,
                        created_recommendations=created,
                    )

            await asyncio.gather(
                *[_run_candidate(candidate) for candidate in candidates]
            )
            await self._set_succeeded_status(
                client_id,
                f"Completed. candidates={total_candidates}, recommendations={created}.",
            )
        except Exception as exc:
            await self._set_failed_status(
                client_id, message="AI selection failed.", error=str(exc)
            )
            raise

    async def _collect_candidates(
        self, watchlist: list, risk_profile: str, client_id: str
    ) -> list[Candidate]:
        candidates: list[Candidate] = []
        total_watchlist = len(watchlist)
        for idx, item in enumerate(watchlist, start=1):
            progress = 10 + int((idx / max(1, total_watchlist)) * 45)
            await self._set_running_status(
                client_id,
                step="collecting_candidates",
                progress=progress,
                message=f"Collecting market/news data ({idx}/{total_watchlist}): {item.symbol}.",
                total_watchlist=total_watchlist,
            )
            bars_15m = self.market_provider.get_15m_bars(item.symbol)
            bars_daily = self.market_provider.get_daily_bars(item.symbol)
            news = await self.news_provider.get_recent_news(
                item.symbol, item.name, hours=24
            )
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
    ) -> bool:
        with get_db() as db:
            last_rec = repository.get_last_recommendation(
                db, client_id, candidate.symbol
            )
        if last_rec and is_cooldown_hit(
            {
                "symbol": last_rec.symbol,
                "action": last_rec.action,
                "created_at": last_rec.created_at,
            },
            candidate.symbol,
            candidate.action_hint,
        ):
            return False

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
            return False
        if not is_reversal_allowed(
            {"action": last_rec.action} if last_rec else None,
            recommendation.action,
            recommendation.confidence,
        ):
            return False
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
        return True

    def _finalize_recommendation(
        self,
        output: LlmOutput,
        action_hint: str,
        market_features: list[dict],
        news_items: list[dict],
    ) -> LlmOutput:
        action = (
            output.action if output.action in {"buy", "sell", "hold"} else action_hint
        )
        evidence = output.evidence or {}
        evidence.setdefault("market_features", market_features[:4])
        evidence.setdefault("news_citations", news_items[:4])
        risk = output.risk or {}
        risk.setdefault("invalidate_conditions", ["signal_invalidated"])
        return LlmOutput(
            summary_zh=output.summary_zh or "信号已触发，请结合风险偏好判断。",
            summary_en=output.summary_en
            or "Signal triggered. Evaluate with your risk profile.",
            action=action,
            target_position_pct=output.target_position_pct,
            risk=risk,
            evidence=evidence,
            confidence=output.confidence,
        )
