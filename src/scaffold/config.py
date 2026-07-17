"""Application configuration loaded from environment variables / .env file."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings.

    Every value can be provided via environment variable (case-insensitive)
    or a local ``.env`` file. See ``.env.example`` for documentation.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Telegram ---
    telegram_bot_token: str = Field(description="Bot token from @BotFather")
    telegram_allowed_user_ids: list[int] = Field(
        default_factory=list,
        description="Telegram user IDs allowed to talk to the bot (empty = deny all)",
    )

    # --- Models / APIs ---
    google_api_key: str = Field(description="Gemini API key (AI Studio)")
    gemini_model: str = Field(
        default="gemini-2.5-flash",
        description="Default Gemini model used by agents",
    )
    fal_key: str = Field(
        default="",
        description="fal.ai API key (required for video rendering, phase 3)",
    )

    # --- Content pipeline ---
    video_backend: str = Field(
        default="stub",
        description="Video renderer: 'stub' (free ffmpeg test clips) or 'fal' (fal.ai)",
    )
    fal_video_model: str = Field(
        default="fal-ai/wan/v2.2-5b/text-to-video",
        description="fal.ai model endpoint used for text-to-video",
    )
    fal_image_video_model: str = Field(
        default="fal-ai/wan/v2.2-5b/image-to-video",
        description="fal.ai model endpoint used for image-to-video (/custom)",
    )
    rss_feeds: list[str] = Field(
        default=[
            "https://feeds.bbci.co.uk/news/world/rss.xml",
            "https://www.theguardian.com/world/rss",
            "https://feeds.arstechnica.com/arstechnica/science",
            "https://www.space.com/feeds/all",
        ],
        description="RSS feeds harvested for news",
    )

    # --- Runtime ---
    app_name: str = Field(default="agent-scaffold")
    data_dir: Path = Field(
        default=Path("data"),
        description="Directory for the session database and generated artifacts",
    )

    # --- Logging ---
    log_level: str = Field(default="INFO")
    log_json: bool = Field(default=False, description="Emit JSON logs (recommended in prod)")

    @field_validator("telegram_allowed_user_ids", mode="before")
    @classmethod
    def _parse_user_ids(cls, value: object) -> object:
        """Allow a single ID or a comma-separated string, e.g. ``123,456``."""
        if isinstance(value, int):
            return [value]
        if isinstance(value, str) and not value.strip().startswith("["):
            return [int(part) for part in value.split(",") if part.strip()]
        return value

    @field_validator("rss_feeds", mode="before")
    @classmethod
    def _parse_feeds(cls, value: object) -> object:
        """Allow a comma-separated string of feed URLs."""
        if isinstance(value, str) and not value.strip().startswith("["):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @property
    def session_db_url(self) -> str:
        """Async SQLAlchemy URL for the ADK session database."""
        return f"sqlite+aiosqlite:///{self.data_dir / 'sessions.db'}"

    @property
    def artifact_dir(self) -> Path:
        return self.data_dir / "artifacts"

    @property
    def output_dir(self) -> Path:
        """Where finished content jobs (videos, captions, manifests) land."""
        return self.data_dir / "output"


def load_settings() -> Settings:
    """Load settings, creating runtime directories as a side effect."""
    # Required fields are populated from the environment at runtime.
    settings = Settings()  # type: ignore[call-arg]
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.artifact_dir.mkdir(parents=True, exist_ok=True)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    return settings
