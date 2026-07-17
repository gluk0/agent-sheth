"""Tests for the Telegram allowlist middleware and reply chunking."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from aiogram.types import TelegramObject

from scaffold.channels.telegram.handlers import _chunks, brew_prompt, parse_custom_caption
from scaffold.channels.telegram.middleware import AllowlistMiddleware


async def _run_middleware(allowed: set[int], user_id: int | None) -> bool:
    """Return True if the handler was invoked."""
    middleware = AllowlistMiddleware(allowed)
    called = False

    async def handler(event: TelegramObject, data: dict[str, Any]) -> None:
        nonlocal called
        called = True

    user = None
    if user_id is not None:
        user = MagicMock()
        user.id = user_id
    data: dict[str, Any] = {"event_from_user": user}
    await middleware(handler, TelegramObject(), data)
    return called


async def test_allowed_user_passes() -> None:
    assert await _run_middleware({111}, 111) is True


async def test_unknown_user_rejected() -> None:
    assert await _run_middleware({111}, 999) is False


async def test_missing_user_rejected() -> None:
    assert await _run_middleware({111}, None) is False


async def test_empty_allowlist_rejects_everyone() -> None:
    assert await _run_middleware(set(), 111) is False


def test_chunks_short_text_untouched() -> None:
    assert _chunks("hello") == ["hello"]


def test_chunks_splits_on_newlines() -> None:
    text = "a" * 10 + "\n" + "b" * 10
    assert _chunks(text, size=15) == ["a" * 10, "b" * 10]


def test_chunks_hard_splits_without_newlines() -> None:
    text = "x" * 25
    assert _chunks(text, size=10) == ["x" * 10, "x" * 10, "x" * 5]


def test_brew_prompt_with_topic() -> None:
    prompt = brew_prompt("ufo hearings")
    assert "stoner news content pipeline" in prompt
    assert "ufo hearings" in prompt


def test_brew_prompt_without_topic() -> None:
    prompt = brew_prompt(None)
    assert "stoner news content pipeline" in prompt
    assert "best current story" in prompt


def test_parse_custom_caption_valid() -> None:
    assert parse_custom_caption("/custom neon smoke, slow zoom") == "neon smoke, slow zoom"


def test_parse_custom_caption_whitespace() -> None:
    assert parse_custom_caption("  /custom   spinning vortex  ") == "spinning vortex"


def test_parse_custom_caption_missing_prompt() -> None:
    assert parse_custom_caption("/custom") is None
    assert parse_custom_caption("/custom   ") is None


def test_parse_custom_caption_not_a_command() -> None:
    assert parse_custom_caption("just a nice photo") is None
    assert parse_custom_caption(None) is None
