from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Content-Relay"
    environment: str = "development"
    log_level: str = "INFO"
    source_urls: list[str] = Field(default_factory=list)
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4o-mini"
    openai_temperature: float = 0.3
    openai_max_tokens: int = 1200
    openai_request_timeout_seconds: float = 45.0
    openai_max_retries: int = 3
    telegram_bot_token: SecretStr | None = None
    telegram_chat_id: str | None = None
    telegram_parse_mode: str = "HTML"
    telegram_admin_ids: list[int] = Field(default_factory=list)
    poll_interval_seconds: int = 900
    scraper_timeout_seconds: float = 45.0
    scraper_max_retries: int = 2
    browser_headless: bool = True
    browser_locale: str = "ru-RU"
    browser_timezone: str = "Europe/Moscow"
    browser_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    )
    prompts_path: Path = Path("core/prompts.yaml")
    max_concurrency: int = 2
    data_dir: Path = Path("data")
    log_dir: Path = Path("logs")

    @field_validator("source_urls", mode="before")
    @classmethod
    def parse_source_urls(cls, value: Any) -> list[str]:
        if value in (None, "", []):
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            if text.startswith("["):
                try:
                    decoded = json.loads(text)
                except json.JSONDecodeError:
                    decoded = None
                if isinstance(decoded, list):
                    return [str(item).strip() for item in decoded if str(item).strip()]
            return [item.strip() for item in text.split(",") if item.strip()]
        return [str(value).strip()]

    @field_validator("telegram_admin_ids", mode="before")
    @classmethod
    def parse_telegram_admin_ids(cls, value: Any) -> list[int]:
        if value in (None, "", []):
            return []
        if isinstance(value, list):
            result: list[int] = []
            for item in value:
                try:
                    result.append(int(item))
                except (TypeError, ValueError):
                    continue
            return result
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            if text.startswith("["):
                try:
                    decoded = json.loads(text)
                except json.JSONDecodeError:
                    decoded = None
                if isinstance(decoded, list):
                    return [int(item) for item in decoded if str(item).strip()]
            return [int(item.strip()) for item in text.split(",") if item.strip()]
        return [int(value)]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
