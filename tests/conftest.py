"""Shared fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from scaffold.config import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    s = Settings(
        _env_file=None,  # type: ignore[call-arg]
        telegram_bot_token="123:test-token",
        telegram_allowed_user_ids=[111],
        google_api_key="test-key",
        data_dir=tmp_path / "data",
    )
    s.data_dir.mkdir(parents=True, exist_ok=True)
    s.artifact_dir.mkdir(parents=True, exist_ok=True)
    return s
