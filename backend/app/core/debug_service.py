from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy import text

from app.core.config import settings
from app.db.database import get_db


class DebugService:
    def __init__(self, market_provider, news_provider, ws_manager) -> None:
        self.market_provider = market_provider
        self.news_provider = news_provider
        self.ws_manager = ws_manager
        self.logger = logging.getLogger("stock_ai_debug")

    async def run_checks(self, client_id: str | None = None) -> dict:
        checks = {
            "llm": await self._check_llm_provider(),
            "market_data": self._check_market_data_provider(),
            "news_data": await self._check_news_provider(),
            "database": self._check_database(),
            "services": await self._check_other_services(),
        }
        ok = all(item.get("ok", False) for item in checks.values())
        result = {
            "ok": ok,
            "timestamp": datetime.now(UTC).isoformat(),
            "checks": checks,
        }
        summary = self._build_summary(result)
        payload = {"summary": summary, "result": result}

        self.logger.info("DEBUG_CHECK %s", json.dumps(payload, ensure_ascii=False))
        print(f"[DEBUG] {summary}")

        try:
            if client_id:
                await self.ws_manager.send_event(client_id, "server.debug.result", payload)
            else:
                await self.ws_manager.broadcast_event("server.debug.result", payload)
        except Exception as error:
            self.logger.warning("failed to push debug result to clients: %s", error)

        return payload

    async def _check_llm_provider(self) -> dict:
        if not settings.llm_api_key:
            return {
                "ok": False,
                "message": "LLM_API_KEY 未配置，无法发送 test 请求",
                "response": "",
            }
        request_body = {
            "model": settings.llm_model,
            "messages": [{"role": "user", "content": "test"}],
            "temperature": 0,
        }
        url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
        try:
            async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
                response = await client.post(url, headers=headers, json=request_body)
            if response.status_code >= 400:
                return {
                    "ok": False,
                    "message": f"LLM 请求失败: HTTP {response.status_code}",
                    "response": response.text[:300],
                }
            data = response.json()
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            return {
                "ok": bool(content),
                "message": "LLM test 请求已发送",
                "response": str(content)[:500],
            }
        except Exception as error:
            return {
                "ok": False,
                "message": f"LLM 请求异常: {error}",
                "response": "",
            }

    def _check_market_data_provider(self) -> dict:
        symbol = "600000"
        try:
            bars_15m = self.market_provider.get_15m_bars(symbol, limit=16)
            bars_daily = self.market_provider.get_daily_bars(symbol, limit=16)
            ok = bool(bars_15m) and bool(bars_daily)
            return {
                "ok": ok,
                "message": "AkShare 行情接口检查完成",
                "symbol": symbol,
                "bars_15m_count": len(bars_15m),
                "bars_daily_count": len(bars_daily),
            }
        except Exception as error:
            return {
                "ok": False,
                "message": f"AkShare 接口异常: {error}",
                "symbol": symbol,
            }

    async def _check_news_provider(self) -> dict:
        symbol = "600000"
        name = "浦发银行"
        try:
            items = await self.news_provider.get_recent_news(symbol=symbol, name=name, hours=24)
            return {
                "ok": True,
                "message": "资讯抓取接口检查完成",
                "symbol": symbol,
                "items_count": len(items),
                "sample_title": items[0]["title"] if items else "",
            }
        except Exception as error:
            return {
                "ok": False,
                "message": f"资讯接口异常: {error}",
                "symbol": symbol,
            }

    def _check_database(self) -> dict:
        try:
            with get_db() as db:
                value = db.execute(text("SELECT 1")).scalar()
            return {
                "ok": value == 1,
                "message": "数据库连接正常",
            }
        except Exception as error:
            return {
                "ok": False,
                "message": f"数据库异常: {error}",
            }

    async def _check_other_services(self) -> dict:
        try:
            online_clients = await self.ws_manager.online_clients_count()
            return {
                "ok": True,
                "message": "服务状态检查完成",
                "scheduler_enabled": settings.scheduler_enabled,
                "scan_interval_minutes": settings.scan_interval_minutes,
                "online_clients": online_clients,
            }
        except Exception as error:
            return {
                "ok": False,
                "message": f"服务状态检查异常: {error}",
            }

    def _build_summary(self, result: dict) -> str:
        checks = result.get("checks", {})
        failed = [name for name, item in checks.items() if not item.get("ok", False)]
        if not failed:
            return "调试检查完成：全部服务正常"
        return f"调试检查完成：失败项 -> {', '.join(failed)}"
