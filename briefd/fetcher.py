"""Content fetchers for Briefd — HN and GitHub Trending."""

from __future__ import annotations

import asyncio
import re

import httpx

from briefd.models import SourceType, Story

HN_BASE = "https://hacker-news.firebaseio.com/v0"
GITHUB_TRENDING_URL = "https://github.com/trending"


async def fetch_hn_top(limit: int = 20) -> list[Story]:
    """Fetch top stories from Hacker News.

    Retrieves the top `limit` stories (skipping jobs, polls, and items
    without a URL). Scores and comment counts are included.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{HN_BASE}/topstories.json")
        resp.raise_for_status()
        ids: list[int] = resp.json()

    # Fetch items concurrently, but cap at limit * 2 to handle skips
    candidate_ids = ids[: limit * 2]
    items = await _fetch_hn_items(candidate_ids)

    stories: list[Story] = []
    for item in items:
        if len(stories) >= limit:
            break
        story = _hn_item_to_story(item)
        if story is not None:
            stories.append(story)

    return stories


async def _fetch_hn_items(ids: list[int]) -> list[dict]:
    async def fetch_one(client: httpx.AsyncClient, item_id: int) -> dict:
        resp = await client.get(f"{HN_BASE}/item/{item_id}.json")
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    async with httpx.AsyncClient(timeout=10) as client:
        tasks = [fetch_one(client, id_) for id_ in ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    return [r for r in results if isinstance(r, dict)]


def _hn_item_to_story(item: dict) -> Story | None:
    """Convert a raw HN item to a Story, or None if it should be skipped."""
    if item.get("type") != "story":
        return None
    url = item.get("url", "")
    if not url:
        return None
    return Story(
        title=item.get("title", ""),
        url=url,
        source=SourceType.HN_TOP,
        score=item.get("score", 0),
        comment_count=item.get("descendants", 0),
    )


async def fetch_github_trending(
    language: str | None = None,
    limit: int = 25,
) -> list[Story]:
    """Scrape GitHub Trending page for popular repos.

    GitHub doesn't have a public trending API, so we scrape the HTML.
    Each article.Box-row element represents one trending repo.
    """
    url = GITHUB_TRENDING_URL
    if language:
        url = f"{url}/{language}"

    async with httpx.AsyncClient(
        timeout=15,
        headers={"User-Agent": "briefd/0.1 (+https://zarpa-cat.github.io)"},
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        html = resp.text

    return _parse_github_trending(html, limit)


def _parse_github_trending(html: str, limit: int) -> list[Story]:
    """Extract repo stories from GitHub Trending HTML."""
    stories: list[Story] = []

    # Match each trending repo block
    # Pattern: <h2 ...><a href="/owner/repo">owner / repo</a></h2>
    repo_pattern = re.compile(
        r'<article[^>]*class="[^"]*Box-row[^"]*"[^>]*>.*?'
        r'<h2[^>]*>\s*<a\s+href="(/[^"]+)"[^>]*>(.*?)</a>',
        re.DOTALL,
    )
    desc_pattern = re.compile(r'<p[^>]*class="[^"]*col-9[^"]*"[^>]*>\s*(.*?)\s*</p>', re.DOTALL)

    for match in repo_pattern.finditer(html):
        if len(stories) >= limit:
            break
        path = match.group(1).strip()
        raw_name = match.group(2).strip()
        # Clean up "owner / repo" → "owner/repo"
        name = re.sub(r"\s*/\s*", "/", raw_name).strip()
        full_url = f"https://github.com{path}"

        # Try to find a description nearby (best effort)
        desc_match = desc_pattern.search(html[match.start() : match.start() + 2000])
        description = ""
        if desc_match:
            description = re.sub(r"<[^>]+>", "", desc_match.group(1)).strip()

        stories.append(
            Story(
                title=name,
                url=full_url,
                source=SourceType.GITHUB_TRENDING,
                summary=description or None,
            )
        )

    return stories
