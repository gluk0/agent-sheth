"""Tests for scaffold.config."""

from __future__ import annotations

from pathlib import Path

from scaffold.config import Settings


def _make(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "telegram_bot_token": "t",
        "google_api_key": "g",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)  # type: ignore[arg-type, call-arg]


def test_defaults() -> None:
    s = _make()
    assert s.gemini_model == "gemini-2.5-flash"
    assert s.telegram_allowed_user_ids == []
    assert s.data_dir == Path("data")


def test_user_ids_from_comma_separated_string() -> None:
    s = _make(telegram_allowed_user_ids="123, 456,789")
    assert s.telegram_allowed_user_ids == [123, 456, 789]


def test_user_ids_from_single_int() -> None:
    # pydantic-settings JSON-parses "1" from the env into a bare int.
    s = _make(telegram_allowed_user_ids=1)
    assert s.telegram_allowed_user_ids == [1]


def test_user_ids_from_list() -> None:
    s = _make(telegram_allowed_user_ids=[1, 2])
    assert s.telegram_allowed_user_ids == [1, 2]


def test_session_db_url_and_artifact_dir(tmp_path: Path) -> None:
    s = _make(data_dir=tmp_path)
    assert s.session_db_url == f"sqlite+aiosqlite:///{tmp_path}/sessions.db"
    assert s.artifact_dir == tmp_path / "artifacts"
