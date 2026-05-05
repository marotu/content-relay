from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field


class ParsedArticle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_url: str
    title: str
    content: str
    description: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    site_name: str | None = None
    language: str | None = None
    keywords: list[str] = Field(default_factory=list)


class ArticleRewrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_url: str
    source_title: str
    title: str
    summary: str
    body: str
    hashtags: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TelegramPostDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_url: str
    title: str
    telegram_text: str
    hashtags: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
