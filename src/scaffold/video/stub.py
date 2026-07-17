"""Free dry-run backend: renders ffmpeg test-pattern clips (or placeholders).

Lets the whole pipeline run end-to-end - including Telegram video delivery -
without spending anything on a real text-to-video model.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from scaffold.logging import get_logger
from scaffold.video.base import RenderError

logger = get_logger(__name__)

_SIZES = {"9:16": "720x1280", "16:9": "1280x720", "1:1": "960x960"}


class StubBackend:
    """Renders a test-pattern clip per shot; writes the prompt alongside it."""

    name = "stub"

    async def render_clip(
        self,
        *,
        prompt: str,
        duration_seconds: float,
        aspect_ratio: str,
        out_path: Path,
    ) -> Path:
        out_path.with_suffix(".prompt.txt").write_text(prompt, encoding="utf-8")

        if shutil.which("ffmpeg") is None:
            logger.warning("stub.no_ffmpeg", hint="writing placeholder bytes instead of video")
            out_path.write_bytes(b"stub-video-placeholder")
            return out_path

        size = _SIZES.get(aspect_ratio, _SIZES["9:16"])
        args = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=duration={duration_seconds}:size={size}:rate=24",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(out_path),
        ]
        await _run_ffmpeg(args)
        logger.info("stub.rendered", path=str(out_path), seconds=duration_seconds)
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
        """Animate a still image with a slow Ken Burns zoom (free, local)."""
        out_path.with_suffix(".prompt.txt").write_text(prompt, encoding="utf-8")

        if shutil.which("ffmpeg") is None:
            logger.warning("stub.no_ffmpeg", hint="writing placeholder bytes instead of video")
            out_path.write_bytes(b"stub-video-placeholder")
            return out_path

        size = _SIZES.get(aspect_ratio, _SIZES["9:16"])
        width, height = size.split("x")
        frames = max(int(duration_seconds * 24), 1)
        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            f"zoompan=z='min(1+0.15*on/{frames},1.15)':d={frames}:s={size}:fps=24"
        )
        args = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(image_path),
            "-t",
            str(duration_seconds),
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(out_path),
        ]
        await _run_ffmpeg(args)
        logger.info("stub.rendered_from_image", path=str(out_path), seconds=duration_seconds)
        return out_path


async def _run_ffmpeg(args: list[str]) -> None:
    process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        msg = f"ffmpeg failed ({process.returncode}): {stderr.decode(errors='replace')[-400:]}"
        raise RenderError(msg)
