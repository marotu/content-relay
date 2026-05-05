from __future__ import annotations

import asyncio
from collections.abc import Iterable

from loguru import logger

from core.config import Settings
from core.exceptions import ContentRelayError
from handlers.publisher import TelegramPublisher
from scrapers.playwright_scraper import PlaywrightArticleScraper
from services.openai_service import OpenAIRewriteService


async def process_source(url: str, settings: Settings) -> None:
    async with PlaywrightArticleScraper(settings=settings) as scraper:
        article = await scraper.scrape(url)

    openai_service = OpenAIRewriteService(settings=settings)
    rewrite = await openai_service.rewrite_article(article)
    telegram_draft = await openai_service.build_telegram_post(rewrite)

    publisher = TelegramPublisher(settings=settings)
    await publisher.send_post(telegram_draft)


async def run_pipeline(urls: Iterable[str], settings: Settings) -> None:
    url_list = [url for url in urls if url.strip()]
    if not url_list:
        logger.warning("No source URLs configured. Nothing to process.")
        return

    semaphore = asyncio.Semaphore(settings.max_concurrency)

    async def guarded_process(url: str) -> None:
        async with semaphore:
            try:
                await process_source(url, settings)
            except ContentRelayError as exc:
                logger.error("Content relay pipeline failed for {}: {}", url, exc)

    await asyncio.gather(*(guarded_process(url) for url in url_list))


async def run_scheduler(settings: Settings) -> None:
    while True:
        await run_pipeline(settings.source_urls, settings)
        await asyncio.sleep(settings.poll_interval_seconds)
