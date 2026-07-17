"""The /custom flow: user-supplied image + raw text -> rendered video.

Deterministic - no LLM stages. The image seeds the video, the text is used
verbatim as the motion prompt and the caption. Jobs land in the same output
layout as pipeline reels so /jobs and /job work on them too.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scaffold.agents.stoner_news.models import ContentJob, Shot
from scaffold.agents.stoner_news.packager import make_job_id
from scaffold.logging import get_logger
from scaffold.video.base import VideoBackend
from scaffold.video.stitch import stitch_clips

logger = get_logger(__name__)


@dataclass(slots=True)
class CustomVideoResult:
    job_id: str
    video_path: Path
    caption: str


async def create_custom_video(
    *,
    prompt: str,
    backend: VideoBackend,
    output_dir: Path,
    image_path: Path | None = None,
    duration_seconds: float = 8.0,
    aspect_ratio: str = "9:16",
) -> CustomVideoResult:
    """Render one video from a raw text prompt, optionally seeded by an image."""
    job = ContentJob(
        topic="custom",
        headline=prompt[:100],
        caption=prompt,
        aspect_ratio=aspect_ratio,
        shots=[Shot(index=0, prompt=prompt, duration_seconds=duration_seconds)],
    )
    job_id = make_job_id(f"custom {prompt}")
    job_dir = output_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "job.json").write_text(job.model_dump_json(indent=2), encoding="utf-8")
    (job_dir / "caption.txt").write_text(job.caption_block, encoding="utf-8")

    logger.info("custom.rendering", job_id=job_id, backend=backend.name, image=bool(image_path))
    if image_path is not None:
        clip = await backend.render_clip_from_image(
            prompt=prompt,
            image_path=image_path,
            duration_seconds=duration_seconds,
            aspect_ratio=aspect_ratio,
            out_path=job_dir / "clip_00.mp4",
        )
    else:
        clip = await backend.render_clip(
            prompt=prompt,
            duration_seconds=duration_seconds,
            aspect_ratio=aspect_ratio,
            out_path=job_dir / "clip_00.mp4",
        )
    final = await stitch_clips([clip], job_dir / "final.mp4")
    logger.info("custom.done", job_id=job_id, path=str(final))
    return CustomVideoResult(job_id=job_id, video_path=final, caption=job.caption_block)
