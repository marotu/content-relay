from __future__ import annotations


class ContentRelayError(Exception):
    """Base exception for the Content-Relay project."""


class ScraperError(ContentRelayError):
    """Raised when article scraping fails."""


class ScraperTimeoutError(ScraperError):
    """Raised when a page cannot be loaded within the configured timeout."""


class ScraperParseError(ScraperError):
    """Raised when article content cannot be extracted from the page."""


class PromptCatalogError(ContentRelayError):
    """Raised when the prompt catalog cannot be loaded or validated."""


class PromptNotFoundError(PromptCatalogError):
    """Raised when a requested prompt template is missing from the catalog."""


class OpenAIServiceError(ContentRelayError):
    """Raised when the OpenAI service cannot complete a request."""


class OpenAIResponseError(OpenAIServiceError):
    """Raised when the OpenAI API returns malformed or incomplete data."""


class OpenAIRetryExhaustedError(OpenAIServiceError):
    """Raised when all retry attempts for an OpenAI request are exhausted."""
