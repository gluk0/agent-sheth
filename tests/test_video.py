"""Tests for the video backends and stitcher."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

import scaffold.video.fal as fal_module
from scaffold.config import Settings
from scaffold.video import FalBackend, StubBackend, create_backend
from scaffold.video.base import RenderError
from scaffold.video.stitch import build_concat_command, stitch_clips

ffmpeg_required = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")


# --- backend factory ---------------------------------------------------------


def test_create_backend_stub(settings: Settings) -> None:
    assert isinstance(create_backend(settings), StubBackend)


def test_create_backend_fal(settings: Settings) -> None:
    settings.video_backend = "fal"
    settings.fal_key = "key"
    assert isinstance(create_backend(settings), FalBackend)


def test_create_backend_fal_requires_key(settings: Settings) -> None:
    settings.video_backend = "fal"
    settings.fal_key = ""
    with pytest.raises(ValueError, match="FAL_KEY"):
        create_backend(settings)


def test_create_backend_unknown(settings: Settings) -> None:
    settings.video_backend = "nope"
    with pytest.raises(ValueError, match="Unknown video backend"):
        create_backend(settings)


# --- stub backend ------------------------------------------------------------


@ffmpeg_required
async def test_stub_renders_real_clip(tmp_path: Path) -> None:
    out = tmp_path / "clip.mp4"
    result = await StubBackend().render_clip(
        prompt="cosmic nebula", duration_seconds=0.5, aspect_ratio="9:16", out_path=out
    )
    assert result == out
    assert out.stat().st_size > 0
    assert out.with_suffix(".prompt.txt").read_text() == "cosmic nebula"


async def test_stub_without_ffmpeg_writes_placeholder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("scaffold.video.stub.shutil.which", lambda _: None)
    out = tmp_path / "clip.mp4"
    await StubBackend().render_clip(
        prompt="p", duration_seconds=1, aspect_ratio="9:16", out_path=out
    )
    assert out.read_bytes() == b"stub-video-placeholder"


@ffmpeg_required
async def test_stub_renders_clip_from_image(tmp_path: Path) -> None:
    # Make a real source image with ffmpeg first.
    import asyncio

    image = tmp_path / "src.png"
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=duration=0.1:size=320x568:rate=1",
        "-frames:v",
        "1",
        str(image),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.communicate()
    assert image.is_file()

    out = tmp_path / "clip.mp4"
    result = await StubBackend().render_clip_from_image(
        prompt="slow cosmic zoom",
        image_path=image,
        duration_seconds=0.5,
        aspect_ratio="9:16",
        out_path=out,
    )
    assert result.stat().st_size > 0
    assert out.with_suffix(".prompt.txt").read_text() == "slow cosmic zoom"


# --- stitcher ------------------------------------------------------------------


async def test_stitch_single_clip_copies(tmp_path: Path) -> None:
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"video-bytes")
    out = tmp_path / "final.mp4"
    assert await stitch_clips([clip], out) == out
    assert out.read_bytes() == b"video-bytes"


async def test_stitch_empty_rejected(tmp_path: Path) -> None:
    with pytest.raises(RenderError, match="No clips"):
        await stitch_clips([], tmp_path / "final.mp4")


def test_concat_command_shape(tmp_path: Path) -> None:
    cmd = build_concat_command(tmp_path / "list.txt", tmp_path / "final.mp4")
    assert cmd[0] == "ffmpeg"
    assert "concat" in cmd
    assert str(tmp_path / "final.mp4") == cmd[-1]


@ffmpeg_required
async def test_stitch_multiple_real_clips(tmp_path: Path) -> None:
    backend = StubBackend()
    clips = [
        await backend.render_clip(
            prompt=f"shot {i}",
            duration_seconds=0.5,
            aspect_ratio="9:16",
            out_path=tmp_path / f"clip_{i}.mp4",
        )
        for i in range(2)
    ]
    out = await stitch_clips(clips, tmp_path / "final.mp4")
    assert out.stat().st_size > 0


# --- fal backend ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"video": {"url": "https://x/v.mp4"}}, "https://x/v.mp4"),
        ({"video": "https://x/v.mp4"}, "https://x/v.mp4"),
        ({"video_url": "https://x/v.mp4"}, "https://x/v.mp4"),
        ({"videos": [{"url": "https://x/v.mp4"}]}, "https://x/v.mp4"),
        ({"something": "else"}, None),
        ("not a dict", None),
    ],
)
def test_fal_extract_video_url(payload: object, expected: str | None) -> None:
    assert FalBackend._extract_video_url(payload) == expected


async def test_fal_render_clip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    submitted: dict[str, Any] = {}

    async def fake_subscribe(application: str, arguments: dict[str, Any]) -> dict[str, Any]:
        submitted["application"] = application
        submitted["arguments"] = arguments
        return {"video": {"url": "https://fal.example/v.mp4"}}

    async def fake_download(url: str, out_path: Path) -> None:
        assert url == "https://fal.example/v.mp4"
        out_path.write_bytes(b"rendered")

    monkeypatch.setattr(fal_module.fal_client, "subscribe_async", fake_subscribe)
    backend = FalBackend(api_key="k", model="fal-ai/test-model")
    monkeypatch.setattr(FalBackend, "_download", staticmethod(fake_download))

    out = tmp_path / "clip.mp4"
    result = await backend.render_clip(
        prompt="neon capitol, vhs grain", duration_seconds=8, aspect_ratio="9:16", out_path=out
    )
    assert result.read_bytes() == b"rendered"
    assert submitted["application"] == "fal-ai/test-model"
    assert submitted["arguments"]["prompt"] == "neon capitol, vhs grain"
    assert submitted["arguments"]["aspect_ratio"] == "9:16"


async def test_fal_render_wraps_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(application: str, arguments: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("quota exceeded")

    monkeypatch.setattr(fal_module.fal_client, "subscribe_async", boom)
    backend = FalBackend(api_key="k", model="m")
    with pytest.raises(RenderError, match="quota exceeded"):
        await backend.render_clip(
            prompt="p", duration_seconds=8, aspect_ratio="9:16", out_path=tmp_path / "c.mp4"
        )


async def test_fal_render_rejects_missing_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def no_url(application: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return {"detail": "done but no video"}

    monkeypatch.setattr(fal_module.fal_client, "subscribe_async", no_url)
    backend = FalBackend(api_key="k", model="m")
    with pytest.raises(RenderError, match="no video URL"):
        await backend.render_clip(
            prompt="p", duration_seconds=8, aspect_ratio="9:16", out_path=tmp_path / "c.mp4"
        )


async def test_fal_render_clip_from_image(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    submitted: dict[str, Any] = {}

    async def fake_upload(path: Path) -> str:
        assert Path(path).name == "photo.jpg"
        return "https://fal.example/uploads/photo.jpg"

    async def fake_subscribe(application: str, arguments: dict[str, Any]) -> dict[str, Any]:
        submitted["application"] = application
        submitted["arguments"] = arguments
        return {"video": {"url": "https://fal.example/v.mp4"}}

    async def fake_download(url: str, out_path: Path) -> None:
        out_path.write_bytes(b"rendered")

    monkeypatch.setattr(fal_module.fal_client, "upload_file_async", fake_upload)
    monkeypatch.setattr(fal_module.fal_client, "subscribe_async", fake_subscribe)
    monkeypatch.setattr(FalBackend, "_download", staticmethod(fake_download))

    image = tmp_path / "photo.jpg"
    image.write_bytes(b"jpeg")
    backend = FalBackend(api_key="k", model="t2v-model", image_model="i2v-model")
    result = await backend.render_clip_from_image(
        prompt="make it swirl",
        image_path=image,
        duration_seconds=8,
        aspect_ratio="9:16",
        out_path=tmp_path / "clip.mp4",
    )
    assert result.read_bytes() == b"rendered"
    assert submitted["application"] == "i2v-model"
    assert submitted["arguments"]["prompt"] == "make it swirl"
    assert submitted["arguments"]["image_url"] == "https://fal.example/uploads/photo.jpg"


async def test_fal_image_model_defaults_to_text_model() -> None:
    backend = FalBackend(api_key="k", model="only-model")
    assert backend._image_model == "only-model"
