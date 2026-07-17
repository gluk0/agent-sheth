"""Stitch rendered clips into the final reel with ffmpeg."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from scaffold.logging import get_logger
from scaffold.video.base import RenderError

logger = get_logger(__name__)


async def stitch_clips(clips: list[Path], out_path: Path) -> Path:
    """Concatenate ``clips`` (same codec/resolution) into ``out_path``."""
    if not clips:
        msg = "No clips to stitch"
        raise RenderError(msg)

    if len(clips) == 1:
        shutil.copyfile(clips[0], out_path)
        return out_path

    if shutil.which("ffmpeg") is None:
        msg = "ffmpeg is required to stitch multiple clips but was not found on PATH"
        raise RenderError(msg)

    list_file = out_path.with_suffix(".concat.txt")
    list_file.write_text("".join(f"file '{clip.resolve()}'\n" for clip in clips), encoding="utf-8")
    args = build_concat_command(list_file, out_path)
    process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await process.communicate()
    list_file.unlink(missing_ok=True)
    if process.returncode != 0:
        msg = f"ffmpeg concat failed ({process.returncode}): "
        msg += stderr.decode(errors="replace")[-400:]
        raise RenderError(msg)

    logger.info("stitch.done", clips=len(clips), path=str(out_path))
    return out_path


def build_concat_command(list_file: Path, out_path: Path) -> list[str]:
    return [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-c",
        "copy",
        str(out_path),
    ]
