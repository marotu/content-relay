from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.filters.command import CommandObject
from aiogram.types import Message
from loguru import logger

from core.config import Settings
from core.exceptions import ContentRelayError
from services.pipeline import process_source


def build_router() -> Router:
    router = Router()

    @router.message(Command("start"))
    async def start_handler(message: Message, settings: Settings) -> None:
        await message.answer(_build_start_message(settings))

    @router.message(Command("status"))
    async def status_handler(message: Message, settings: Settings) -> None:
        await message.answer(_build_status_message(settings))

    @router.message(Command("publish"))
    async def publish_handler(message: Message, command: CommandObject, settings: Settings) -> None:
        if not _is_authorized(message, settings):
            await message.answer("Access denied: configure telegram_admin_ids for your user ID.")
            return

        url = _extract_url(command.args)
        if url is None:
            await message.answer("Usage: /publish <url>")
            return

        try:
            await process_source(url, settings)
        except ContentRelayError as exc:
            logger.error("Manual publish failed for {}: {}", url, exc)
            await message.answer(f"Publication failed: {exc}")
            return

        await message.answer(f"Published successfully: {url}")

    return router


def _is_authorized(message: Message, settings: Settings) -> bool:
    if message.from_user is None:
        return False
    if not settings.telegram_admin_ids:
        return False
    return message.from_user.id in settings.telegram_admin_ids


def _extract_url(arguments: str | None) -> str | None:
    if not arguments:
        return None
    candidate = arguments.strip().split(maxsplit=1)[0]
    if candidate.startswith("http://") or candidate.startswith("https://"):
        return candidate
    return None


def _build_start_message(settings: Settings) -> str:
    source_count = len(settings.source_urls)
    admin_count = len(settings.telegram_admin_ids)
    return (
        f"{settings.app_name}\n"
        f"Sources configured: {source_count}\n"
        f"Admin IDs configured: {admin_count}\n"
        "Commands: /status, /publish <url>"
    )


def _build_status_message(settings: Settings) -> str:
    return (
        f"Environment: {settings.environment}\n"
        f"Poll interval: {settings.poll_interval_seconds}s\n"
        f"Concurrency: {settings.max_concurrency}\n"
        f"Sources configured: {len(settings.source_urls)}"
    )
