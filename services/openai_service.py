from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Final

from loguru import logger
from openai import APIConnectionError, APIError, APITimeoutError, AsyncOpenAI, RateLimitError
from pydantic import ValidationError

from core.config import Settings, get_settings
from core.exceptions import OpenAIRetryExhaustedError, OpenAIResponseError, OpenAIServiceError
from core.models import ArticleRewrite, ParsedArticle, TelegramPostDraft
from core.prompts import PromptCatalog, PromptTemplate, load_prompts, render_template


@dataclass(slots=True)
class _OpenAIRequest:
    system_prompt: str
    user_prompt: str


class OpenAIRewriteService:
    _RETRYABLE_EXCEPTIONS: Final[tuple[type[BaseException], ...]] = (
        RateLimitError,
        APITimeoutError,
        APIConnectionError,
        asyncio.TimeoutError,
    )

    def __init__(self, settings: Settings | None = None, prompts: PromptCatalog | None = None) -> None:
        self.settings = settings or get_settings()
        self.prompts = prompts or load_prompts(self.settings.prompts_path)
        if self.settings.openai_api_key is None:
            raise OpenAIServiceError("OpenAI API key is not configured.")
        self.client = AsyncOpenAI(
            api_key=self.settings.openai_api_key.get_secret_value(),
            timeout=self.settings.openai_request_timeout_seconds,
            max_retries=0,
        )

    async def rewrite_article(self, article: ParsedArticle) -> ArticleRewrite:
        prompt = self.prompts.rewrite_article_prompt()
        request = _OpenAIRequest(
            system_prompt=prompt.system,
            user_prompt=render_template(
                prompt.user,
                article_json=json.dumps(article.model_dump(mode="json"), ensure_ascii=False, indent=2),
            ),
        )
        payload = await self._chat_json(request)
        return self._build_article_rewrite(article, payload)

    async def build_telegram_post(self, rewrite: ArticleRewrite) -> TelegramPostDraft:
        prompt = self.prompts.rewrite_telegram_prompt()
        request = _OpenAIRequest(
            system_prompt=prompt.system,
            user_prompt=render_template(
                prompt.user,
                rewrite_json=json.dumps(rewrite.model_dump(mode="json"), ensure_ascii=False, indent=2),
            ),
        )
        payload = await self._chat_json(request)
        return self._build_telegram_post(rewrite, payload)

    async def _chat_json(self, request: _OpenAIRequest) -> dict[str, Any]:
        last_error: BaseException | None = None
        delay_seconds = 1.5

        for attempt in range(1, self.settings.openai_max_retries + 1):
            try:
                response = await self.client.chat.completions.create(
                    model=self.settings.openai_model,
                    temperature=self.settings.openai_temperature,
                    max_tokens=self.settings.openai_max_tokens,
                    messages=[
                        {"role": "system", "content": request.system_prompt},
                        {"role": "user", "content": request.user_prompt},
                    ],
                    response_format={"type": "json_object"},
                )
                content = response.choices[0].message.content or ""
                if not content.strip():
                    raise OpenAIResponseError("OpenAI returned an empty response payload.")

                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError as exc:
                    raise OpenAIResponseError("OpenAI returned invalid JSON content.") from exc

                if not isinstance(parsed, dict):
                    raise OpenAIResponseError("OpenAI JSON response must be an object.")

                return parsed
            except self._RETRYABLE_EXCEPTIONS as exc:
                last_error = exc
                logger.warning(
                    "OpenAI request failed on attempt {}/{}: {}",
                    attempt,
                    self.settings.openai_max_retries,
                    exc,
                )
                if attempt == self.settings.openai_max_retries:
                    raise OpenAIRetryExhaustedError("OpenAI request retries were exhausted.") from exc
                await asyncio.sleep(delay_seconds)
                delay_seconds *= 2
            except APIError as exc:
                raise OpenAIServiceError(f"OpenAI API returned a non-retryable error: {exc}") from exc

        if last_error is not None:
            raise OpenAIRetryExhaustedError("OpenAI request retries were exhausted.") from last_error

        raise OpenAIServiceError("OpenAI request failed unexpectedly.")

    def _build_article_rewrite(self, article: ParsedArticle, payload: dict[str, Any]) -> ArticleRewrite:
        try:
            return ArticleRewrite.model_validate(
                {
                    "source_url": article.source_url,
                    "source_title": article.title,
                    "title": payload["title"],
                    "summary": payload["summary"],
                    "body": payload["body"],
                    "hashtags": self._normalize_hashtags(payload.get("hashtags", [])),
                }
            )
        except KeyError as exc:
            raise OpenAIResponseError(f"Missing required field in OpenAI article payload: {exc.args[0]}") from exc
        except ValidationError as exc:
            raise OpenAIResponseError("Invalid OpenAI article payload shape.") from exc

    def _build_telegram_post(self, rewrite: ArticleRewrite, payload: dict[str, Any]) -> TelegramPostDraft:
        try:
            return TelegramPostDraft.model_validate(
                {
                    "source_url": rewrite.source_url,
                    "title": rewrite.title,
                    "telegram_text": payload["telegram_text"],
                    "hashtags": self._normalize_hashtags(payload.get("hashtags", [])),
                }
            )
        except KeyError as exc:
            raise OpenAIResponseError(f"Missing required field in OpenAI telegram payload: {exc.args[0]}") from exc
        except ValidationError as exc:
            raise OpenAIResponseError("Invalid OpenAI telegram payload shape.") from exc

    @staticmethod
    def _normalize_hashtags(value: Any) -> list[str]:
        if isinstance(value, list):
            candidates = value
        elif isinstance(value, str):
            candidates = value.split()
        else:
            candidates = []

        hashtags: list[str] = []
        for candidate in candidates:
            normalized = str(candidate).strip().lstrip("#")
            if normalized:
                hashtags.append(normalized)
        return list(dict.fromkeys(hashtags))
