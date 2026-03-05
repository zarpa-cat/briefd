"""Tests for content fetchers."""

from __future__ import annotations

import httpx
import respx

from briefd.fetcher import fetch_github_trending, fetch_hn_top
from briefd.models import SourceType

HN_TOPSTORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{id}.json"


class TestFetchHNTop:
    @respx.mock
    async def test_returns_stories_with_correct_source(self) -> None:
        respx.get(HN_TOPSTORIES_URL).mock(return_value=httpx.Response(200, json=[1, 2, 3]))
        for i in [1, 2, 3]:
            respx.get(f"https://hacker-news.firebaseio.com/v0/item/{i}.json").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "id": i,
                        "title": f"Story {i}",
                        "url": f"https://example.com/{i}",
                        "score": i * 10,
                        "descendants": i * 2,
                        "type": "story",
                    },
                )
            )

        stories = await fetch_hn_top(limit=3)
        assert len(stories) == 3
        assert all(s.source == SourceType.HN_TOP for s in stories)

    @respx.mock
    async def test_stories_have_title_url_score(self) -> None:
        respx.get(HN_TOPSTORIES_URL).mock(return_value=httpx.Response(200, json=[42]))
        respx.get("https://hacker-news.firebaseio.com/v0/item/42.json").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": 42,
                    "title": "Show HN: My cool project",
                    "url": "https://cool.example.com",
                    "score": 250,
                    "descendants": 80,
                    "type": "story",
                },
            )
        )

        stories = await fetch_hn_top(limit=1)
        assert stories[0].title == "Show HN: My cool project"
        assert stories[0].url == "https://cool.example.com"
        assert stories[0].score == 250
        assert stories[0].comment_count == 80

    @respx.mock
    async def test_skips_non_story_items(self) -> None:
        """Jobs and ask HN with no URL should be skipped."""
        respx.get(HN_TOPSTORIES_URL).mock(return_value=httpx.Response(200, json=[1, 2]))
        respx.get("https://hacker-news.firebaseio.com/v0/item/1.json").mock(
            return_value=httpx.Response(
                200,
                json={"id": 1, "title": "Job posting", "type": "job"},
            )
        )
        respx.get("https://hacker-news.firebaseio.com/v0/item/2.json").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": 2,
                    "title": "Real story",
                    "url": "https://real.com",
                    "score": 100,
                    "descendants": 10,
                    "type": "story",
                },
            )
        )

        stories = await fetch_hn_top(limit=5)
        assert len(stories) == 1
        assert stories[0].title == "Real story"

    @respx.mock
    async def test_respects_limit(self) -> None:
        respx.get(HN_TOPSTORIES_URL).mock(return_value=httpx.Response(200, json=list(range(1, 21))))
        for i in range(1, 6):
            respx.get(f"https://hacker-news.firebaseio.com/v0/item/{i}.json").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "id": i,
                        "title": f"Story {i}",
                        "url": f"https://example.com/{i}",
                        "score": 100,
                        "descendants": 5,
                        "type": "story",
                    },
                )
            )

        stories = await fetch_hn_top(limit=5)
        assert len(stories) == 5


class TestFetchGitHubTrending:
    @respx.mock
    async def test_returns_stories_with_correct_source(self) -> None:
        # GitHub trending scrape — mock the HTML response
        html = """
        <article class="Box-row">
          <h2 class="h3"><a href="/rust-lang/rust">rust-lang / rust</a></h2>
          <p>Empowering everyone to build reliable software.</p>
        </article>
        <article class="Box-row">
          <h2 class="h3"><a href="/python/cpython">python / cpython</a></h2>
          <p>The Python programming language.</p>
        </article>
        """
        respx.get("https://github.com/trending").mock(return_value=httpx.Response(200, text=html))

        stories = await fetch_github_trending(limit=10)
        assert len(stories) == 2
        assert all(s.source == SourceType.GITHUB_TRENDING for s in stories)

    @respx.mock
    async def test_github_url_is_full_url(self) -> None:
        html = """
        <article class="Box-row">
          <h2 class="h3"><a href="/zarpa-cat/briefd">zarpa-cat / briefd</a></h2>
          <p>A briefing tool.</p>
        </article>
        """
        respx.get("https://github.com/trending").mock(return_value=httpx.Response(200, text=html))

        stories = await fetch_github_trending(limit=5)
        assert stories[0].url == "https://github.com/zarpa-cat/briefd"
