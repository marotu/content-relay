from __future__ import annotations

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError
from loguru import logger

from core.config import Settings
from core.exceptions import ContentRelayError
from core.models import TelegramPostDraft


class TelegramPublisher:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        if self.settings.telegram_bot_token is None:
            raise ContentRelayError("Telegram bot token is not configured.")
        if not self.settings.telegram_chat_id:
            raise ContentRelayError("Telegram chat ID is not configured.")

    async def send_post(self, draft: TelegramPostDraft) -> None:
        bot = Bot(token=self.settings.telegram_bot_token.get_secret_value())
        try:
            await bot.send_message(
                chat_id=self.settings.telegram_chat_id,
                text=self._compose_message(draft),
                parse_mode=self.settings.telegram_parse_mode,
                disable_web_page_preview=True,
            )
            logger.info("Published Telegram post for {}", draft.source_url)
        except TelegramBadRequest as exc:
            raise ContentRelayError(f"Telegram rejected the post payload: {exc}") from exc
        except TelegramForbiddenError as exc:
            raise ContentRelayError(f"Telegram bot has no access to target chat: {exc}") from exc
        except TelegramNetworkError as exc:
            raise ContentRelayError(f"Telegram network error while sending post: {exc}") from exc
        finally:
            await bot.session.close()

    def _compose_message(self, draft: TelegramPostDraft) -> str:
        parts = [draft.telegram_text.strip()]
        if draft.hashtags:
            parts.append("")
            parts.append(" ".join(f"#{tag.lstrip('#')}" for tag in draft.hashtags))
        parts.append("")
        parts.append(f"Источник: {draft.source_url}")
        return "\n".join(parts).strip()
