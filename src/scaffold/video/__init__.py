"""Video rendering backends."""

from scaffold.config import Settings
from scaffold.video.base import RenderError, VideoBackend
from scaffold.video.fal import FalBackend
from scaffold.video.stub import StubBackend

__all__ = ["FalBackend", "RenderError", "StubBackend", "VideoBackend", "create_backend"]


def create_backend(settings: Settings) -> VideoBackend:
    """Build the configured video backend."""
    match settings.video_backend:
        case "stub":
            return StubBackend()
        case "fal":
            if not settings.fal_key:
                msg = "video_backend='fal' requires FAL_KEY to be set"
                raise ValueError(msg)
            return FalBackend(
                api_key=settings.fal_key,
                model=settings.fal_video_model,
                image_model=settings.fal_image_video_model,
            )
        case other:
            msg = f"Unknown video backend: {other!r} (expected 'stub' or 'fal')"
            raise ValueError(msg)
