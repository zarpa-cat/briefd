"""Briefing pipeline — filter stories and generate digest."""

from __future__ import annotations

import httpx

from briefd.billing import CustomerStatus
from briefd.models import Briefing, BriefingStatus, Story, UserConfig


def filter_stories(stories: list[Story], cfg: UserConfig) -> list[Story]:
    """Filter stories to those matching the user's topics, capped at max_stories."""
    matched = [s for s in stories if s.is_relevant(cfg.topics)]
    return matched[: cfg.max_stories]


def _build_prompt(stories: list[Story], topics: list[str], date: str) -> str:
    """Build the LLM prompt for daily digest generation."""
    topic_str = ", ".join(topics)
    if not stories:
        story_block = "(No stories matched today's topics.)"
    else:
        lines = []
        for i, s in enumerate(stories, 1):
            score_info = f" [{s.score} pts]" if s.score else ""
            lines.append(f"{i}. **{s.title}**{score_info}\n   {s.url}")
        story_block = "\n\n".join(lines)

    return f"""You are Briefd, a concise technical digest writer.
Date: {date}
Topics: {topic_str}

Here are today's top stories on these topics:

{story_block}

Write a clean, scannable daily digest in Markdown. For each story, write 1-2 sentences
explaining why it matters. Group thematically if helpful. Lead with the most interesting.
Skip filler phrases. Be direct. Readers are busy developers.

End with a one-line "takeaway" section summarising the day's theme.
"""


async def call_llm(prompt: str) -> str:
    """Call the LLM API to generate a digest.

    Uses the Anthropic API if ANTHROPIC_API_KEY is set,
    otherwise raises to trigger FAILED status in tests / graceful degradation.
    """
    import os

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise OSError("ANTHROPIC_API_KEY not set")

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"]  # type: ignore[index]


async def generate_briefing_gated(
    cfg: UserConfig,
    stories: list[Story],
    date: str,
    customer_status: CustomerStatus,
) -> Briefing:
    """Generate a briefing only if the customer has access (premium or credits).

    Returns a FAILED briefing immediately if access is denied — no LLM call made.
    """
    briefing = Briefing(
        user_id=cfg.user_id,
        date=date,
        topics=cfg.topics,
        stories=stories,
    )

    if not customer_status.can_afford_briefing:
        briefing.status = BriefingStatus.FAILED
        return briefing

    return await generate_briefing(cfg, stories, date)


async def generate_briefing(
    cfg: UserConfig,
    stories: list[Story],
    date: str,
) -> Briefing:
    """Generate a complete briefing for a user.

    Builds the LLM prompt from the filtered stories, calls the LLM,
    and returns a Briefing in READY or FAILED state.
    """
    briefing = Briefing(
        user_id=cfg.user_id,
        date=date,
        topics=cfg.topics,
        stories=stories,
    )
    briefing.status = BriefingStatus.GENERATING

    try:
        prompt = _build_prompt(stories, cfg.topics, date)
        digest = await call_llm(prompt)
        briefing.mark_ready(digest)
    except Exception:
        briefing.status = BriefingStatus.FAILED

    return briefing
