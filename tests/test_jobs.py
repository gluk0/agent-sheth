"""Tests for the job listing helpers."""

from __future__ import annotations

import json
from pathlib import Path

from scaffold.jobs import get_job, list_jobs


def _write_job(output_dir: Path, job_id: str, headline: str, with_video: bool = True) -> None:
    job_dir = output_dir / job_id
    job_dir.mkdir(parents=True)
    (job_dir / "job.json").write_text(
        json.dumps({"headline": headline, "shots": [{"index": 0, "prompt": "p"}]})
    )
    (job_dir / "caption.txt").write_text(f"caption for {headline}")
    if with_video:
        (job_dir / "final.mp4").write_bytes(b"v")


def test_list_jobs_empty(tmp_path: Path) -> None:
    assert list_jobs(tmp_path / "missing") == []


def test_list_jobs_most_recent_first(tmp_path: Path) -> None:
    _write_job(tmp_path, "20260716-120000-older", "Old story")
    _write_job(tmp_path, "20260717-120000-newer", "New story", with_video=False)
    (tmp_path / "not-a-job").mkdir()  # ignored: no manifest

    jobs = list_jobs(tmp_path)
    assert [j.job_id for j in jobs] == ["20260717-120000-newer", "20260716-120000-older"]
    assert jobs[0].video_path is None
    assert jobs[1].video_path is not None
    assert jobs[1].headline == "Old story"
    assert jobs[1].shots == 1


def test_list_jobs_respects_limit(tmp_path: Path) -> None:
    for i in range(5):
        _write_job(tmp_path, f"20260717-12000{i}-job", f"Story {i}")
    assert len(list_jobs(tmp_path, limit=3)) == 3


def test_get_job(tmp_path: Path) -> None:
    _write_job(tmp_path, "20260717-120000-x", "Story X")
    job = get_job(tmp_path, "20260717-120000-x")
    assert job is not None
    assert job.headline == "Story X"
    assert job.caption_block == "caption for Story X"
    assert get_job(tmp_path, "nope") is None
