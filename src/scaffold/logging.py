"""Structured logging setup (structlog on top of stdlib logging)."""

from __future__ import annotations

import logging
import sys

import structlog


def setup_logging(level: str = "INFO", json_output: bool = False) -> None:
    """Configure structlog + stdlib logging for the whole process."""
    renderer: structlog.typing.Processor
    if json_output:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(sys.stderr),
        cache_logger_on_first_use=True,
    )

    # Keep noisy third-party stdlib loggers in check.
    logging.basicConfig(level=level.upper(), stream=sys.stderr, format="%(message)s")
    for noisy in ("httpx", "aiogram.event", "google_genai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]
