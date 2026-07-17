"""Tests for the packager stage, run through the real ADK Runner."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.sessions import InMemorySessionService

import scaffold.agents.stoner_news.packager as packager_module
from scaffold.agents.stoner_news.packager import (
    STATE_CONTENT_JOB,
    PackagerAgent,
    make_job_id,
)
from scaffold.config import Settings
from scaffold.runtime import AgentReply, AgentRuntime

_VALID_JOB = {
    "topic": "ufo",
    "headline": "Congress holds UFO hearing",
    "caption": "bro they had a whole hearing",
    "hashtags": ["aliens", "ufo"],
    "shots": [
        {"index": 1, "prompt": "retro capitol, vhs grain", "duration_seconds": 6},
        {"index": 0, "prompt": "cosmic nebula, slow zoom", "duration_seconds": 8},
    ],
}


class FakeBackend:
    name = "fake"

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.prompts: list[str] = []

    async def render_clip(
        self, *, prompt: str, duration_seconds: float, aspect_ratio: str, out_path: Path
    ) -> Path:
        if self.fail:
            from scaffold.video.base import RenderError

            raise RenderError("backend exploded")
        self.prompts.append(prompt)
        out_path.write_bytes(b"clip")
        return out_path

    async def render_clip_from_image(
        self,
        *,
        prompt: str,
        image_path: Path,
        duration_seconds: float,
        aspect_ratio: str,
        out_path: Path,
    ) -> Path:
        out_path.write_bytes(b"image-clip")
        return out_path


@pytest.fixture(autouse=True)
def fake_stitch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fake clips aren't real video, so replace the ffmpeg stitcher."""

    async def _stitch(clips: list[Path], out_path: Path) -> Path:
        out_path.write_bytes(b"".join(c.read_bytes() for c in clips))
        return out_path

    monkeypatch.setattr(packager_module, "stitch_clips", _stitch)


async def _run_packager(
    settings: Settings, backend: FakeBackend, state: dict[str, object]
) -> list[AgentReply]:
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=settings.app_name, user_id="u1", session_id="c1", state=state
    )
    runtime = AgentRuntime(
        settings,
        agent=PackagerAgent(name="packager", backend=backend, output_dir=settings.output_dir),
        session_service=session_service,
        artifact_service=InMemoryArtifactService(),
    )
    return [r async for r in runtime.run_turn(user_id="u1", session_id="c1", text="go")]


def test_make_job_id_is_sortable_and_sluggy() -> None:
    job_id = make_job_id("Congress holds UFO hearing!", datetime(2026, 7, 17, 12, 30, 5))
    assert job_id == "20260717-123005-congress-holds-ufo-hearing"


async def test_packager_renders_and_reports(settings: Settings) -> None:
    backend = FakeBackend()
    replies = await _run_packager(settings, backend, {STATE_CONTENT_JOB: _VALID_JOB})

    assert len(replies) == 1
    reply = replies[0]
    assert reply.video_path is not None
    assert reply.video_path.name == "final.mp4"
    assert reply.video_path.is_file()
    assert "Reel ready" in reply.text
    assert "#aliens #ufo" in reply.text

    # Shots rendered in index order despite shuffled input.
    assert backend.prompts == ["cosmic nebula, slow zoom", "retro capitol, vhs grain"]

    job_dir = reply.video_path.parent
    assert (job_dir / "job.json").is_file()
    assert "#aliens" in (job_dir / "caption.txt").read_text()


async def test_packager_accepts_json_string_state(settings: Settings) -> None:
    import json

    replies = await _run_packager(
        settings, FakeBackend(), {STATE_CONTENT_JOB: json.dumps(_VALID_JOB)}
    )
    assert replies[0].video_path is not None


async def test_packager_rejects_invalid_job(settings: Settings) -> None:
    replies = await _run_packager(settings, FakeBackend(), {STATE_CONTENT_JOB: {"topic": "x"}})
    assert len(replies) == 1
    assert replies[0].video_path is None
    assert "failed validation" in replies[0].text


async def test_packager_missing_state(settings: Settings) -> None:
    replies = await _run_packager(settings, FakeBackend(), {})
    assert replies[0].video_path is None
    assert "failed validation" in replies[0].text


async def test_packager_reports_render_failure(settings: Settings) -> None:
    replies = await _run_packager(settings, FakeBackend(fail=True), {STATE_CONTENT_JOB: _VALID_JOB})
    assert len(replies) == 1
    assert replies[0].video_path is None
    assert "Rendering failed" in replies[0].text
    assert "backend exploded" in replies[0].text
