from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import time
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_mode: str = os.getenv("MANAGER_OS_MODE", "direct")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    openai_reasoning_effort: str = os.getenv("OPENAI_REASONING_EFFORT", "low")
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_timezone_name: str = os.getenv("TELEGRAM_TIMEZONE", "Europe/Moscow")
    morning_reset_time: str = os.getenv("MORNING_RESET_TIME", "09:00")
    evening_review_time: str = os.getenv("EVENING_REVIEW_TIME", "18:30")
    weekly_review_day: int = int(os.getenv("WEEKLY_REVIEW_DAY", "6"))
    weekly_review_time: str = os.getenv("WEEKLY_REVIEW_TIME", "19:00")

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key.strip())

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token.strip())

    @property
    def telegram_timezone(self) -> ZoneInfo:
        return ZoneInfo(self.telegram_timezone_name)

    def parse_clock(self, value: str) -> time:
        hours, minutes = value.split(":", 1)
        return time(hour=int(hours), minute=int(minutes), tzinfo=self.telegram_timezone)


settings = Settings()
