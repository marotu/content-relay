from __future__ import annotations

import asyncio
import sys
from contextlib import suppress

from aiogram import Bot, Dispatcher
from loguru import logger

from core.config import Settings, get_settings
from core.exceptions import ContentRelayError
from handlers.router import build_router
from services.pipeline import run_scheduler


def configure_logging(settings: Settings) -> None:
    logger.remove()
    logger.add(
        sink=sys.stderr,
        level=settings.log_level.upper(),
        backtrace=False,
        diagnose=False,
        enqueue=True,
    )


def validate_settings(settings: Settings) -> None:
    missing: list[str] = []
    if settings.openai_api_key is None:
        missing.append("OPENAI_API_KEY")
    if settings.telegram_bot_token is None:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not settings.telegram_chat_id:
        missing.append("TELEGRAM_CHAT_ID")

    if missing:
        raise ContentRelayError(f"Missing required settings: {', '.join(missing)}")


async def run_application(settings: Settings) -> None:
    validate_settings(settings)

    bot = Bot(token=settings.telegram_bot_token.get_secret_value())
    dispatcher = Dispatcher()
    dispatcher["settings"] = settings
    dispatcher.include_router(build_router())

    scheduler_task = asyncio.create_task(run_scheduler(settings))
    try:
        await dispatcher.start_polling(bot)
    finally:
        scheduler_task.cancel()
        with suppress(asyncio.CancelledError):
            await scheduler_task
        await bot.session.close()


async def amain() -> None:
    settings = get_settings()
    configure_logging(settings)
    await run_application(settings)


if __name__ == "__main__":
    asyncio.run(amain())
