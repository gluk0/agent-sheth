"""Tests for the RSS news tools."""

from __future__ import annotations

import pytest

import scaffold.agents.stoner_news.tools as tools_module
from scaffold.agents.stoner_news.models import NewsItem
from scaffold.agents.stoner_news.tools import build_rss_tool, parse_feed, strip_html

_SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Weird News Wire</title>
    <item>
      <title>Mysterious lights over Nevada desert</title>
      <link>https://example.com/lights</link>
      <description>&lt;p&gt;Witnesses report &lt;b&gt;strange&lt;/b&gt; lights.&lt;/p&gt;
      </description>
      <pubDate>Fri, 17 Jul 2026 08:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Senator proposes bill about balloons</title>
      <link>https://example.com/balloons</link>
      <description>A bill. About balloons.</description>
    </item>
    <item>
      <title></title>
      <link>https://example.com/empty-title-skipped</link>
    </item>
  </channel>
</rss>
"""


def test_strip_html() -> None:
    assert strip_html("<p>hello <b>world</b></p>") == "hello world"


def test_parse_feed_normalizes_items() -> None:
    items = parse_feed(_SAMPLE_RSS, "https://example.com/feed")
    assert len(items) == 2  # empty-title entry skipped
    first = items[0]
    assert first.title == "Mysterious lights over Nevada desert"
    assert first.url == "https://example.com/lights"
    assert first.source == "Weird News Wire"
    assert first.summary == "Witnesses report strange lights."
    assert "2026" in first.published


def test_parse_feed_garbage_yields_nothing() -> None:
    assert parse_feed("not xml at all", "https://example.com/feed") == []


async def test_rss_tool_reports_items(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch(urls: list[str]) -> list[NewsItem]:
        assert urls == ["https://example.com/feed"]
        return [NewsItem(title="A story", url="https://example.com/a")]

    monkeypatch.setattr(tools_module, "fetch_feeds", fake_fetch)
    tool = build_rss_tool(["https://example.com/feed"])
    result = await tool()
    assert result["status"] == "success"
    assert result["count"] == 1
    assert result["items"][0]["title"] == "A story"


async def test_rss_tool_reports_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch(urls: list[str]) -> list[NewsItem]:
        return []

    monkeypatch.setattr(tools_module, "fetch_feeds", fake_fetch)
    tool = build_rss_tool(["https://example.com/feed"])
    result = await tool()
    assert result["status"] == "empty"
    assert result["count"] == 0


def test_rss_tool_has_llm_friendly_metadata() -> None:
    tool = build_rss_tool([])
    assert tool.__name__ == "fetch_rss_headlines"
    assert tool.__doc__ is not None and "RSS" in tool.__doc__
