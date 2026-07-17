"""Entrypoint: ``uv run scaffold`` or ``python -m scaffold``."""

from __future__ import annotations

import asyncio
import contextlib

from scaffold.channels.telegram import run_bot
from scaffold.config import load_settings
from scaffold.logging import setup_logging
from scaffold.runtime import AgentRuntime


def main() -> None:
    settings = load_settings()
    setup_logging(settings.log_level, settings.log_json)
    runtime = AgentRuntime(settings)
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run_bot(settings, runtime))


if __name__ == "__main__":
    main()
