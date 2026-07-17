"""Tests for the content pipeline data models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from scaffold.agents.stoner_news.models import ContentJob, Shot


def _job(**overrides: object) -> ContentJob:
    base: dict[str, object] = {
        "topic": "ufo",
        "headline": "Congress holds UFO hearing",
        "caption": "bro they had a whole hearing",
        "shots": [
            {"index": 0, "prompt": "cosmic nebula, slow zoom", "duration_seconds": 8},
            {"index": 1, "prompt": "retro capitol footage, vhs grain", "duration_seconds": 6},
        ],
    }
    base.update(overrides)
    return ContentJob.model_validate(base)


def test_hashtags_are_normalized() -> None:
    job = _job(hashtags=["aliens", "#ufo", " weird ", ""])
    assert job.hashtags == ["#aliens", "#ufo", "#weird"]


def test_caption_block_joins_caption_and_hashtags() -> None:
    job = _job(hashtags=["aliens"])
    assert job.caption_block == "bro they had a whole hearing\n\n#aliens"


def test_caption_block_without_hashtags() -> None:
    assert _job().caption_block == "bro they had a whole hearing"


def test_total_duration() -> None:
    assert _job().total_duration_seconds == 14


def test_at_least_one_shot_required() -> None:
    with pytest.raises(ValidationError):
        _job(shots=[])


def test_shot_duration_capped_at_ten_seconds() -> None:
    with pytest.raises(ValidationError):
        Shot(index=0, prompt="x", duration_seconds=11)


def test_job_roundtrips_through_json() -> None:
    job = _job(hashtags=["aliens"])
    assert ContentJob.model_validate_json(job.model_dump_json()) == job
