"""aiogram middleware."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

from scaffold.logging import get_logger

logger = get_logger(__name__)


class AllowlistMiddleware(BaseMiddleware):
    """Drop every update that does not come from an allowlisted user."""

    def __init__(self, allowed_user_ids: set[int]) -> None:
        self._allowed = allowed_user_ids

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        if user is None or user.id not in self._allowed:
            logger.warning(
                "update.rejected",
                user_id=user.id if user else None,
                username=user.username if user else None,
            )
            return None
        return await handler(event, data)
