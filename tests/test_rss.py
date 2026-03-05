"""Tests for the RSS fetcher."""

from __future__ import annotations

import httpx
import respx

from briefd.fetcher import fetch_rss
from briefd.models import SourceType

RSS_URL = "https://feeds.example.com/tech"

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example Tech Feed</title>
    <link>https://example.com</link>
    <item>
      <title>Python 3.14 Released</title>
      <link>https://example.com/python-314</link>
      <description>The latest Python release ships new features.</description>
    </item>
    <item>
      <title>Rust 2.0 Announced</title>
      <link>https://example.com/rust-2</link>
      <description>Major Rust milestone announced.</description>
    </item>
    <item>
      <title>No Link Item</title>
      <description>This item has no link.</description>
    </item>
  </channel>
</rss>"""


class TestFetchRSS:
    @respx.mock
    async def test_returns_stories_from_valid_feed(self) -> None:
        respx.get(RSS_URL).mock(return_value=httpx.Response(200, text=SAMPLE_RSS))
        stories = await fetch_rss(RSS_URL, limit=10)
        assert len(stories) == 2  # third item has no link, should be skipped

    @respx.mock
    async def test_stories_have_correct_source(self) -> None:
        respx.get(RSS_URL).mock(return_value=httpx.Response(200, text=SAMPLE_RSS))
        stories = await fetch_rss(RSS_URL)
        assert all(s.source == SourceType.RSS for s in stories)

    @respx.mock
    async def test_stories_have_title_and_url(self) -> None:
        respx.get(RSS_URL).mock(return_value=httpx.Response(200, text=SAMPLE_RSS))
        stories = await fetch_rss(RSS_URL)
        assert stories[0].title == "Python 3.14 Released"
        assert stories[0].url == "https://example.com/python-314"

    @respx.mock
    async def test_respects_limit(self) -> None:
        respx.get(RSS_URL).mock(return_value=httpx.Response(200, text=SAMPLE_RSS))
        stories = await fetch_rss(RSS_URL, limit=1)
        assert len(stories) == 1

    @respx.mock
    async def test_returns_empty_on_http_error(self) -> None:
        respx.get(RSS_URL).mock(return_value=httpx.Response(404))
        stories = await fetch_rss(RSS_URL)
        assert stories == []
