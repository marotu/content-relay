from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from core.config import Settings, get_settings
from core.models import ParsedArticle


class BaseArticleScraper(ABC):
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @abstractmethod
    async def scrape(self, url: str) -> ParsedArticle:
        raise NotImplementedError

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        return " ".join(text.split()).strip()

    @classmethod
    def _merge_blocks(cls, blocks: Iterable[str]) -> str:
        normalized_blocks = [
            cls._normalize_whitespace(block)
            for block in blocks
            if cls._normalize_whitespace(block)
        ]
        return "\n\n".join(dict.fromkeys(normalized_blocks))
