"""Data contracts for the stoner news content pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class NewsItem(BaseModel):
    """A normalized headline pulled from RSS or search."""

    title: str
    url: str = ""
    source: str = ""
    summary: str = ""
    published: str = ""


class Shot(BaseModel):
    """One video-generation beat (a single clip)."""

    index: int = Field(ge=0, description="Playback order, starting at 0")
    duration_seconds: float = Field(
        # ge/le (not gt/lt): Gemini structured output rejects exclusiveMinimum.
        default=8.0,
        ge=1,
        le=10,
        description="Clip length; most T2V models cap at 5-10s",
    )
    prompt: str = Field(description="Complete text-to-video prompt for this shot")
    voiceover: str = Field(default="", description="Voiceover line spoken over this shot")


class ContentJob(BaseModel):
    """Everything needed to render and publish one Instagram reel.

    This is the contract between the creative stages (LLM) and the rendering
    layer, and it is fully serializable so a job can be re-rendered against a
    different backend without re-running the LLM stages.
    """

    topic: str = Field(description="Short topic label, e.g. 'UFO hearing fallout'")
    headline: str = Field(description="The real news headline this reel is based on")
    angle: str = Field(default="", description="The stoner take on the story")
    source_urls: list[str] = Field(default_factory=list)
    hook: str = Field(default="", description="First-two-seconds hook line")
    caption: str = Field(description="Instagram caption, ready to paste")
    hashtags: list[str] = Field(default_factory=list)
    voiceover_script: str = Field(default="", description="Full VO script")
    aspect_ratio: str = Field(default="9:16", description="Vertical for reels")
    shots: list[Shot] = Field(min_length=1)

    @field_validator("hashtags", mode="after")
    @classmethod
    def _normalize_hashtags(cls, tags: list[str]) -> list[str]:
        return [t if t.startswith("#") else f"#{t}" for t in (t.strip() for t in tags) if t]

    @property
    def caption_block(self) -> str:
        """Caption plus hashtags, ready to paste into Instagram."""
        parts = [self.caption.strip()]
        if self.hashtags:
            parts.append(" ".join(self.hashtags))
        return "\n\n".join(p for p in parts if p)

    @property
    def total_duration_seconds(self) -> float:
        return sum(shot.duration_seconds for shot in self.shots)
