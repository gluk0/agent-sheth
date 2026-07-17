"""Tests for the /custom image + text -> video flow."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scaffold.custom_video import create_custom_video
from scaffold.jobs import list_jobs
from scaffold.video.base import RenderError


class FakeImageBackend:
    name = "fake"

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict[str, object]] = []

    async def render_clip(
        self, *, prompt: str, duration_seconds: float, aspect_ratio: str, out_path: Path
    ) -> Path:
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
        if self.fail:
            raise RenderError("image backend exploded")
        self.calls.append({"prompt": prompt, "image": image_path, "aspect": aspect_ratio})
        out_path.write_bytes(b"image-clip")
        return out_path


async def test_custom_video_renders_and_persists(tmp_path: Path) -> None:
    image = tmp_path / "photo.jpg"
    image.write_bytes(b"jpeg-bytes")
    backend = FakeImageBackend()
    output_dir = tmp_path / "output"

    result = await create_custom_video(
        image_path=image, prompt="neon smoke, slow zoom", backend=backend, output_dir=output_dir
    )

    assert result.video_path.is_file()
    assert result.video_path.read_bytes() == b"image-clip"
    assert result.caption == "neon smoke, slow zoom"
    assert backend.calls[0]["prompt"] == "neon smoke, slow zoom"
    assert backend.calls[0]["aspect"] == "9:16"

    job_dir = result.video_path.parent
    manifest = json.loads((job_dir / "job.json").read_text())
    assert manifest["topic"] == "custom"
    assert manifest["headline"] == "neon smoke, slow zoom"
    assert len(manifest["shots"]) == 1


async def test_custom_video_visible_via_jobs(tmp_path: Path) -> None:
    image = tmp_path / "photo.jpg"
    image.write_bytes(b"jpeg-bytes")
    output_dir = tmp_path / "output"
    result = await create_custom_video(
        image_path=image, prompt="vortex", backend=FakeImageBackend(), output_dir=output_dir
    )
    jobs = list_jobs(output_dir)
    assert [j.job_id for j in jobs] == [result.job_id]
    assert jobs[0].video_path is not None


async def test_custom_video_propagates_render_errors(tmp_path: Path) -> None:
    image = tmp_path / "photo.jpg"
    image.write_bytes(b"jpeg-bytes")
    with pytest.raises(RenderError, match="image backend exploded"):
        await create_custom_video(
            image_path=image,
            prompt="p",
            backend=FakeImageBackend(fail=True),
            output_dir=tmp_path / "output",
        )
