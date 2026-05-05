from __future__ import annotations

from contextlib import suppress
from datetime import datetime
from typing import Final

from loguru import logger
from playwright.async_api import Browser, BrowserContext, Page, Playwright, TimeoutError as PlaywrightTimeoutError, async_playwright

from core.config import Settings
from core.exceptions import ScraperError, ScraperParseError, ScraperTimeoutError
from core.models import ParsedArticle
from scrapers.base import BaseArticleScraper


class PlaywrightArticleScraper(BaseArticleScraper):
    _ARTICLE_SELECTORS: Final[tuple[str, ...]] = (
        "article",
        "main article",
        "main",
        "[role='main']",
        ".article-content",
        ".post-content",
        ".entry-content",
        ".content",
    )
    _TITLE_SELECTORS: Final[tuple[str, ...]] = (
        "h1",
        "article h1",
        "[itemprop='headline']",
        "meta[property='og:title']",
        "meta[name='twitter:title']",
        "title",
    )
    _DESCRIPTION_SELECTORS: Final[tuple[str, ...]] = (
        "meta[name='description']",
        "meta[property='og:description']",
        "meta[name='twitter:description']",
    )
    _AUTHOR_SELECTORS: Final[tuple[str, ...]] = (
        "[rel='author']",
        "[itemprop='author']",
        "meta[name='author']",
        "meta[property='article:author']",
    )
    _PUBLISHED_SELECTORS: Final[tuple[str, ...]] = (
        "meta[property='article:published_time']",
        "meta[property='og:published_time']",
        "time[datetime]",
        "[itemprop='datePublished']",
    )
    _SITE_NAME_SELECTORS: Final[tuple[str, ...]] = (
        "meta[property='og:site_name']",
        "meta[name='application-name']",
    )
    _KEYWORDS_SELECTORS: Final[tuple[str, ...]] = (
        "meta[name='keywords']",
        "meta[property='article:tag']",
    )
    _HTTP_HEADERS: Final[dict[str, str]] = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-Ch-Ua": '"Chromium";v="125", "Google Chrome";v="125", ";Not A Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Upgrade-Insecure-Requests": "1",
    }

    def __init__(self, settings: Settings | None = None) -> None:
        super().__init__(settings=settings)
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def __aenter__(self) -> PlaywrightArticleScraper:
        await self._ensure_context()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def close(self) -> None:
        if self._context is not None:
            await self._context.close()
            self._context = None

        if self._browser is not None:
            await self._browser.close()
            self._browser = None

        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def scrape(self, url: str) -> ParsedArticle:
        context = await self._ensure_context()
        timeout_ms = int(self.settings.scraper_timeout_seconds * 1000)
        last_error: ScraperError | None = None

        for attempt in range(1, self.settings.scraper_max_retries + 1):
            page: Page | None = None
            try:
                page = await context.new_page()
                page.set_default_navigation_timeout(timeout_ms)
                page.set_default_timeout(timeout_ms)
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                await page.wait_for_timeout(700)
                article = await self._extract_article(page, url)
                logger.info("Scraped article from {}", url)
                return article
            except PlaywrightTimeoutError as exc:
                last_error = ScraperTimeoutError(
                    f"Timed out while loading article '{url}' on attempt {attempt}/{self.settings.scraper_max_retries}."
                )
                logger.warning("{}", last_error)
                if attempt == self.settings.scraper_max_retries:
                    raise last_error from exc
            except (ValueError, ScraperParseError) as exc:
                last_error = ScraperParseError(f"Failed to parse article '{url}' on attempt {attempt}.")
                logger.warning("{}", last_error)
                if attempt == self.settings.scraper_max_retries:
                    raise last_error from exc
            finally:
                if page is not None:
                    with suppress(Exception):
                        await page.close()

        if last_error is not None:
            raise last_error

        raise ScraperError(f"Unable to scrape article '{url}'.")

    async def _ensure_context(self) -> BrowserContext:
        if self._context is not None:
            return self._context

        if self._playwright is None:
            self._playwright = await async_playwright().start()

        if self._browser is None:
            self._browser = await self._playwright.chromium.launch(
                headless=self.settings.browser_headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )

        self._context = await self._browser.new_context(
            user_agent=self.settings.browser_user_agent,
            locale=self.settings.browser_locale,
            timezone_id=self.settings.browser_timezone,
            viewport={"width": 1440, "height": 1080},
            has_touch=False,
            is_mobile=False,
            extra_http_headers=self._HTTP_HEADERS,
        )
        self._context.set_default_timeout(int(self.settings.scraper_timeout_seconds * 1000))
        self._context.set_default_navigation_timeout(int(self.settings.scraper_timeout_seconds * 1000))
        await self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )
        return self._context

    async def _extract_article(self, page: Page, source_url: str) -> ParsedArticle:
        title = await self._extract_title(page)
        content = await self._extract_content(page)
        description = await self._extract_meta_text(page, self._DESCRIPTION_SELECTORS)
        author = await self._extract_author(page)
        published_at = self._parse_datetime(await self._extract_meta_text(page, self._PUBLISHED_SELECTORS))
        site_name = await self._extract_meta_text(page, self._SITE_NAME_SELECTORS)
        language = await self._extract_language(page)
        keywords = await self._extract_keywords(page)

        if not content:
            raise ScraperParseError(f"Empty article content for '{source_url}'.")

        if not title:
            raise ScraperParseError(f"Could not detect article title for '{source_url}'.")

        return ParsedArticle(
            source_url=source_url,
            title=title,
            content=content,
            description=description,
            author=author,
            published_at=published_at,
            site_name=site_name,
            language=language,
            keywords=keywords,
        )

    async def _extract_title(self, page: Page) -> str | None:
        for selector in self._TITLE_SELECTORS:
            text = await self._locator_text(page, selector)
            if text:
                return text

        return None

    async def _extract_content(self, page: Page) -> str:
        for selector in self._ARTICLE_SELECTORS:
            locator = page.locator(selector)
            if await locator.count() == 0:
                continue

            candidate = await self._normalize_candidate(await locator.first.inner_text())
            if len(candidate) >= 400:
                return candidate

        paragraph_blocks: list[str] = []
        for selector in ("article p", "main p", "section p", "p"):
            locator = page.locator(selector)
            if await locator.count() == 0:
                continue
            paragraph_blocks.extend(await locator.all_inner_texts())

        merged_paragraphs = self._merge_blocks(paragraph_blocks)
        if merged_paragraphs:
            return merged_paragraphs

        body_text = self._normalize_whitespace(await page.locator("body").inner_text())
        if len(body_text) >= 300:
            return body_text

        return ""

    async def _extract_meta_text(self, page: Page, selectors: tuple[str, ...]) -> str | None:
        for selector in selectors:
            locator = page.locator(selector)
            if await locator.count() == 0:
                continue

            attribute = "content" if selector.startswith("meta") else None
            if attribute is None:
                text = await self._normalize_candidate(await locator.first.inner_text())
            else:
                value = await locator.first.get_attribute(attribute)
                text = self._normalize_candidate(value or "")

            if text:
                return text

        return None

    async def _extract_author(self, page: Page) -> str | None:
        for selector in self._AUTHOR_SELECTORS:
            locator = page.locator(selector)
            if await locator.count() == 0:
                continue

            if selector.startswith("meta"):
                value = await locator.first.get_attribute("content")
                text = self._normalize_whitespace(value or "")
            else:
                text = self._normalize_whitespace(await locator.first.inner_text())

            if text:
                return text

        return None

    async def _extract_language(self, page: Page) -> str | None:
        html_locator = page.locator("html")
        if await html_locator.count() == 0:
            return None

        language = await html_locator.first.get_attribute("lang")
        return self._normalize_whitespace(language or "") or None

    async def _extract_keywords(self, page: Page) -> list[str]:
        for selector in self._KEYWORDS_SELECTORS:
            locator = page.locator(selector)
            if await locator.count() == 0:
                continue

            if selector.startswith("meta"):
                raw_value = await locator.first.get_attribute("content")
            else:
                raw_value = await locator.first.inner_text()

            keywords = [
                self._normalize_whitespace(item)
                for item in (raw_value or "").split(",")
                if self._normalize_whitespace(item)
            ]
            if keywords:
                return list(dict.fromkeys(keywords))

        return []

    async def _locator_text(self, page: Page, selector: str) -> str | None:
        locator = page.locator(selector)
        if await locator.count() == 0:
            return None

        if selector.startswith("meta"):
            value = await locator.first.get_attribute("content")
            return self._normalize_candidate(value or "")

        if selector == "title":
            title_text = await self._normalize_candidate(await locator.first.inner_text())
            return title_text

        return self._normalize_candidate(await locator.first.inner_text())

    def _normalize_candidate(self, text: str) -> str | None:
        normalized = self._normalize_whitespace(text)
        return normalized or None
