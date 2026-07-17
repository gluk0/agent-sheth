"""Telegram bot bootstrap: wires the dispatcher, middleware, and runtime."""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramAPIError

from scaffold.channels.telegram.handlers import router
from scaffold.channels.telegram.middleware import AllowlistMiddleware
from scaffold.config import Settings
from scaffold.logging import get_logger
from scaffold.runtime import AgentRuntime

logger = get_logger(__name__)


def create_dispatcher(settings: Settings, runtime: AgentRuntime) -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher["runtime"] = runtime
    dispatcher["settings"] = settings
    dispatcher.update.outer_middleware(AllowlistMiddleware(set(settings.telegram_allowed_user_ids)))
    dispatcher.include_router(router)
    return dispatcher


async def run_bot(settings: Settings, runtime: AgentRuntime) -> None:
    """Start long polling. Blocks until interrupted."""
    if not settings.telegram_allowed_user_ids:
        logger.warning("allowlist.empty", hint="set TELEGRAM_ALLOWED_USER_IDS in .env")

    bot = Bot(token=settings.telegram_bot_token)
    dispatcher = create_dispatcher(settings, runtime)
    try:
        try:
            me = await bot.get_me()
        except TelegramAPIError as exc:
            logger.error("bot.auth_failed", error=str(exc), hint="check TELEGRAM_BOT_TOKEN")
            raise SystemExit(1) from exc
        logger.info("bot.started", username=me.username, allowed=settings.telegram_allowed_user_ids)
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()
        await runtime.close()
        logger.info("bot.stopped")
