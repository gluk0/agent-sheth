"""News-gathering tools for the harvester agent."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from typing import Any

import feedparser
import httpx

from scaffold.agents.stoner_news.models import NewsItem
from scaffold.logging import get_logger

logger = get_logger(__name__)

_MAX_ITEMS_PER_FEED = 10
_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    return _TAG_RE.sub("", text).strip()


def parse_feed(content: bytes | str, source_url: str) -> list[NewsItem]:
    """Parse one RSS/Atom document into normalized news items."""
    parsed = feedparser.parse(content)  # type: ignore[attr-defined,no-untyped-call]
    source = str(parsed.feed.get("title", source_url))
    items: list[NewsItem] = []
    for entry in parsed.entries[:_MAX_ITEMS_PER_FEED]:
        title = str(entry.get("title", "")).strip()
        if not title:
            continue
        items.append(
            NewsItem(
                title=title,
                url=str(entry.get("link", "")),
                source=source,
                summary=strip_html(str(entry.get("summary", "")))[:500],
                published=str(entry.get("published", "")),
            )
        )
    return items


async def fetch_feeds(urls: list[str]) -> list[NewsItem]:
    """Fetch all feeds concurrently; failures are logged, not fatal."""

    async def fetch_one(client: httpx.AsyncClient, url: str) -> list[NewsItem]:
        try:
            response = await client.get(url)
            response.raise_for_status()
            return parse_feed(response.content, url)
        except Exception as exc:
            logger.warning("rss.fetch_failed", url=url, error=str(exc))
            return []

    async with httpx.AsyncClient(
        timeout=15, follow_redirects=True, headers={"User-Agent": "agent-scaffold/0.1"}
    ) as client:
        results = await asyncio.gather(*(fetch_one(client, url) for url in urls))
    return [item for feed_items in results for item in feed_items]


def build_rss_tool(feeds: list[str]) -> Callable[[], Awaitable[dict[str, Any]]]:
    """Build the ADK function tool bound to the configured feed list."""

    async def fetch_rss_headlines() -> dict[str, Any]:
        """Fetch current news headlines from the configured RSS feeds.

        Returns a dict with 'count' and 'items'; each item has title, url,
        source, summary, and published fields.
        """
        items = await fetch_feeds(feeds)
        return {
            "status": "success" if items else "empty",
            "count": len(items),
            "items": [item.model_dump() for item in items],
        }

    return fetch_rss_headlines
