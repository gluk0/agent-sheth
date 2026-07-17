"""Packager: the deterministic final pipeline stage.

Validates the ContentJob produced by the LLM stages, persists the job
manifest, renders every shot through the configured video backend, stitches
the final reel, and signals the video path to the channel layer via state.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncGenerator
from datetime import datetime
from pathlib import Path

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types
from pydantic import ConfigDict, ValidationError

from scaffold.agents.stoner_news.models import ContentJob
from scaffold.logging import get_logger
from scaffold.video.base import RenderError, VideoBackend
from scaffold.video.stitch import stitch_clips

logger = get_logger(__name__)

# State keys shared with the runtime/channel layer.
STATE_CONTENT_JOB = "content_job"
STATE_VIDEO_PATH = "last_video_path"
STATE_CAPTION = "last_caption"


def make_job_id(headline: str, now: datetime | None = None) -> str:
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    slug = re.sub(r"[^a-z0-9]+", "-", headline.lower()).strip("-")[:40]
    return f"{stamp}-{slug}" if slug else stamp


class PackagerAgent(BaseAgent):
    """Renders the ContentJob found in session state into a finished reel."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    backend: VideoBackend
    output_dir: Path

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        try:
            job = self._load_job(ctx)
        except (ValidationError, ValueError) as exc:
            logger.warning("packager.invalid_job", error=str(exc))
            yield self._text_event(ctx, f"Content job failed validation: {exc}")
            return

        job_id = make_job_id(job.headline)
        job_dir = self.output_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "job.json").write_text(job.model_dump_json(indent=2), encoding="utf-8")
        (job_dir / "caption.txt").write_text(job.caption_block, encoding="utf-8")

        logger.info(
            "packager.rendering",
            job_id=job_id,
            backend=self.backend.name,
            shots=len(job.shots),
            seconds=job.total_duration_seconds,
        )
        try:
            clips = [
                await self.backend.render_clip(
                    prompt=shot.prompt,
                    duration_seconds=shot.duration_seconds,
                    aspect_ratio=job.aspect_ratio,
                    out_path=job_dir / f"clip_{shot.index:02d}.mp4",
                )
                for shot in sorted(job.shots, key=lambda s: s.index)
            ]
            final = await stitch_clips(clips, job_dir / "final.mp4")
        except RenderError as exc:
            logger.exception("packager.render_failed", job_id=job_id)
            yield self._text_event(
                ctx, f"Rendering failed for job {job_id}: {exc}\nJob manifest kept at {job_dir}."
            )
            return

        summary = (
            f"Reel ready: {job.headline}\n"
            f"Job: {job_id} | {len(job.shots)} shots, "
            f"~{job.total_duration_seconds:.0f}s, backend: {self.backend.name}\n\n"
            f"{job.caption_block}"
        )
        yield self._text_event(
            ctx,
            summary,
            state_delta={STATE_VIDEO_PATH: str(final), STATE_CAPTION: job.caption_block},
        )

    def _load_job(self, ctx: InvocationContext) -> ContentJob:
        raw = ctx.session.state.get(STATE_CONTENT_JOB)
        if raw is None:
            msg = f"no {STATE_CONTENT_JOB!r} found in session state"
            raise ValueError(msg)
        if isinstance(raw, str):
            raw = json.loads(raw)
        return ContentJob.model_validate(raw)

    def _text_event(
        self,
        ctx: InvocationContext,
        text: str,
        state_delta: dict[str, object] | None = None,
    ) -> Event:
        return Event(
            invocation_id=ctx.invocation_id,
            author=self.name,
            content=types.Content(role="model", parts=[types.Part(text=text)]),
            actions=EventActions(state_delta=state_delta or {}),
        )
