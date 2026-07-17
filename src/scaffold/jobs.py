"""Read-only access to finished content jobs on disk."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class JobSummary:
    job_id: str
    headline: str
    caption_block: str
    video_path: Path | None
    shots: int


def _load_one(job_dir: Path) -> JobSummary | None:
    manifest = job_dir / "job.json"
    if not manifest.is_file():
        return None
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    caption_file = job_dir / "caption.txt"
    video = job_dir / "final.mp4"
    return JobSummary(
        job_id=job_dir.name,
        headline=str(data.get("headline", "")),
        caption_block=(caption_file.read_text(encoding="utf-8") if caption_file.is_file() else ""),
        video_path=video if video.is_file() else None,
        shots=len(data.get("shots", [])),
    )


def list_jobs(output_dir: Path, limit: int = 10) -> list[JobSummary]:
    """Most recent jobs first."""
    if not output_dir.is_dir():
        return []
    dirs = sorted((d for d in output_dir.iterdir() if d.is_dir()), reverse=True)
    jobs = (_load_one(d) for d in dirs[:limit])
    return [j for j in jobs if j is not None]


def get_job(output_dir: Path, job_id: str) -> JobSummary | None:
    job_dir = output_dir / job_id
    return _load_one(job_dir) if job_dir.is_dir() else None
