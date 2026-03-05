"""Core data models for Briefd."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class SourceType(Enum):
    HN_TOP = "hn_top"
    GITHUB_TRENDING = "github_trending"
    RSS = "rss"


class BriefingStatus(Enum):
    PENDING = "pending"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


@dataclass
class Story:
    """A single story or item from a content source."""

    title: str
    url: str
    source: SourceType
    score: int = 0
    comment_count: int = 0
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    summary: str | None = None

    def is_relevant(self, topics: list[str]) -> bool:
        """Check if story matches any of the user's topics (case-insensitive)."""
        text = (self.title + " " + (self.url or "")).lower()
        return any(topic.lower() in text for topic in topics)


@dataclass
class Briefing:
    """A generated daily digest for a user."""

    user_id: str
    date: str  # ISO date string: 2026-03-05
    topics: list[str]
    stories: list[Story] = field(default_factory=list)
    digest_markdown: str = ""
    status: BriefingStatus = BriefingStatus.PENDING
    credits_consumed: int = 1
    generated_at: datetime | None = None

    def story_count(self) -> int:
        return len(self.stories)

    def mark_ready(self, digest: str) -> None:
        self.digest_markdown = digest
        self.status = BriefingStatus.READY
        self.generated_at = datetime.now(UTC)


@dataclass
class UserConfig:
    """Per-user preferences for their briefing."""

    user_id: str
    topics: list[str]
    delivery_hour_utc: int = 7  # 07:00 UTC = 08:00 Copenhagen
    sources: list[SourceType] = field(
        default_factory=lambda: [SourceType.HN_TOP, SourceType.GITHUB_TRENDING]
    )
    max_stories: int = 10

    def __post_init__(self) -> None:
        if not 0 <= self.delivery_hour_utc <= 23:
            raise ValueError(f"delivery_hour_utc must be 0-23, got {self.delivery_hour_utc}")
        if not self.topics:
            raise ValueError("At least one topic required")
