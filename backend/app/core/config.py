from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class Settings:
    app_name: str = "stock-ai-backend"
    db_url: str = os.getenv("DB_URL", "sqlite:///./stock_ai.db")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4.1-mini")
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "20"))
    llm_max_concurrency: int = int(os.getenv("LLM_MAX_CONCURRENCY", "20"))
    scheduler_enabled: bool = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"
    scan_interval_minutes: int = int(os.getenv("SCAN_INTERVAL_MINUTES", "15"))
    cooldown_minutes: int = int(os.getenv("COOLDOWN_MINUTES", "240"))
    evidence_min_items: int = int(os.getenv("EVIDENCE_MIN_ITEMS", "2"))
    min_turnover_20d: float = float(os.getenv("MIN_TURNOVER_20D", "100000000"))
    max_position_aggressive: int = int(os.getenv("MAX_POSITION_AGGRESSIVE", "50"))
    max_position_neutral: int = int(os.getenv("MAX_POSITION_NEUTRAL", "35"))
    max_position_conservative: int = int(os.getenv("MAX_POSITION_CONSERVATIVE", "20"))


settings = Settings()
