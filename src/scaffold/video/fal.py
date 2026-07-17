"""fal.ai text-to-video backend."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import fal_client
import httpx

from scaffold.logging import get_logger
from scaffold.video.base import RenderError

logger = get_logger(__name__)


class FalBackend:
    """Renders clips via fal.ai text-to-video / image-to-video endpoints."""

    name = "fal"

    def __init__(self, *, api_key: str, model: str, image_model: str = "") -> None:
        self._model = model
        self._image_model = image_model or model
        # The fal client reads credentials from the environment.
        os.environ.setdefault("FAL_KEY", api_key)

    async def render_clip(
        self,
        *,
        prompt: str,
        duration_seconds: float,
        aspect_ratio: str,
        out_path: Path,
    ) -> Path:
        arguments: dict[str, Any] = {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
        }
        return await self._render(self._model, arguments, out_path, duration_seconds)

    async def render_clip_from_image(
        self,
        *,
        prompt: str,
        image_path: Path,
        duration_seconds: float,
        aspect_ratio: str,
        out_path: Path,
    ) -> Path:
        try:
            image_url = await fal_client.upload_file_async(image_path)
        except Exception as exc:
            msg = f"fal.ai image upload failed: {exc}"
            raise RenderError(msg) from exc
        arguments: dict[str, Any] = {
            "prompt": prompt,
            "image_url": image_url,
        }
        return await self._render(self._image_model, arguments, out_path, duration_seconds)

    async def _render(
        self, model: str, arguments: dict[str, Any], out_path: Path, duration_seconds: float
    ) -> Path:
        logger.info("fal.submit", model=model, seconds=duration_seconds)
        try:
            result = await fal_client.subscribe_async(model, arguments)
        except Exception as exc:  # fal_client raises several error types
            msg = f"fal.ai request failed: {exc}"
            raise RenderError(msg) from exc

        url = self._extract_video_url(result)
        if url is None:
            msg = f"fal.ai response contained no video URL: {result!r}"
            raise RenderError(msg)

        await self._download(url, out_path)
        logger.info("fal.rendered", path=str(out_path))
        return out_path

    @staticmethod
    def _extract_video_url(result: object) -> str | None:
        """Handle the common fal response shapes across video models."""
        if not isinstance(result, dict):
            return None
        video = result.get("video")
        if isinstance(video, dict) and isinstance(video.get("url"), str):
            return str(video["url"])
        if isinstance(video, str):
            return video
        if isinstance(result.get("video_url"), str):
            return str(result["video_url"])
        videos = result.get("videos")
        if isinstance(videos, list) and videos and isinstance(videos[0], dict):
            url = videos[0].get("url")
            if isinstance(url, str):
                return url
        return None

    @staticmethod
    async def _download(url: str, out_path: Path) -> None:
        async with (
            httpx.AsyncClient(timeout=120, follow_redirects=True) as client,
            client.stream("GET", url) as response,
        ):
            response.raise_for_status()
            with out_path.open("wb") as fh:
                async for chunk in response.aiter_bytes():
                    fh.write(chunk)
