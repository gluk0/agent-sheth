"""Video backend protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


class RenderError(RuntimeError):
    """Raised when a backend fails to produce a clip."""


@runtime_checkable
class VideoBackend(Protocol):
    """A text-to-video renderer.

    Implementations render one clip per call; stitching clips into the final
    reel is backend-agnostic and lives in :mod:`scaffold.video.stitch`.
    """

    name: str

    async def render_clip(
        self,
        *,
        prompt: str,
        duration_seconds: float,
        aspect_ratio: str,
        out_path: Path,
    ) -> Path:
        """Render a single clip to ``out_path`` and return it."""
        ...

    async def render_clip_from_image(
        self,
        *,
        prompt: str,
        image_path: Path,
        duration_seconds: float,
        aspect_ratio: str,
        out_path: Path,
    ) -> Path:
        """Render a clip animated from a source image to ``out_path``."""
        ...
