from __future__ import annotations

import asyncio
import json

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.models.schemas import CandidateContext, LlmOutput


PROMPT_TEMPLATE = """
你是A股交易辅助模型。请基于输入的行情特征、资讯证据、风险偏好，输出严格JSON：
{
  "summary_zh": "...",
  "summary_en": "...",
  "action": "buy|sell|hold",
  "target_position_pct": 0-100,
  "risk": {"stop_loss_pct": number, "take_profit_pct": number, "invalidate_conditions": []},
  "evidence": {"market_features": [], "news_citations": []},
  "confidence": 0-1
}
不得输出JSON以外内容。
输入:
{payload}
"""


class LlmClient:
    def __init__(self) -> None:
        self._semaphore = asyncio.Semaphore(settings.llm_max_concurrency)

    async def generate(self, context: CandidateContext) -> LlmOutput:
        payload = context.model_dump(mode="json")
        prompt = PROMPT_TEMPLATE.format(payload=json.dumps(payload, ensure_ascii=False))
        for attempt in (1, 2):
            text = await self._call_llm(prompt)
            try:
                parsed = json.loads(text)
                return LlmOutput.model_validate(parsed)
            except (json.JSONDecodeError, ValidationError):
                if attempt == 2:
                    break
        return self._fallback_output(context)

    async def _call_llm(self, prompt: str) -> str:
        if not settings.llm_api_key:
            return "{}"
        headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
        body = {
            "model": settings.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
        }
        async with self._semaphore:
            async with httpx.AsyncClient(
                timeout=settings.llm_timeout_seconds, follow_redirects=True
            ) as client:
                for _ in range(3):
                    try:
                        response = await client.post(
                            f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                            headers=headers,
                            json=body,
                        )
                    except Exception:
                        await asyncio.sleep(0.5)
                        continue
                    if response.status_code in {429, 500, 502, 503, 504}:
                        await asyncio.sleep(0.6)
                        continue
                    response.raise_for_status()
                    data = response.json()
                    return (
                        data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "{}")
                    )
        return "{}"

    def _fallback_output(self, context: CandidateContext) -> LlmOutput:
        return LlmOutput(
            summary_zh=f"{context.symbol} 当前信号不足，建议观望。",
            summary_en=f"{context.symbol} has insufficient signal; hold for now.",
            action="hold",
            target_position_pct=0.0,
            risk={"invalidate_conditions": ["schema_validation_failed"]},
            evidence={
                "market_features": context.market_features[:2],
                "news_citations": context.news_items[:1],
            },
            confidence=0.1,
        )
