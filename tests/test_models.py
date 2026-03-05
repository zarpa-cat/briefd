"""Tests for core data models."""

from __future__ import annotations

import pytest

from briefd.models import Briefing, BriefingStatus, SourceType, Story, UserConfig


class TestStoryRelevance:
    def test_relevant_when_topic_in_title(self) -> None:
        story = Story(
            title="New Python 3.14 release",
            url="https://python.org",
            source=SourceType.HN_TOP,
        )
        assert story.is_relevant(["python", "rust"]) is True

    def test_not_relevant_when_no_topic_matches(self) -> None:
        story = Story(
            title="Latest football scores",
            url="https://sport.com",
            source=SourceType.HN_TOP,
        )
        assert story.is_relevant(["python", "rust"]) is False

    def test_case_insensitive_match(self) -> None:
        story = Story(
            title="PYTHON performance improvements",
            url="https://example.com",
            source=SourceType.HN_TOP,
        )
        assert story.is_relevant(["Python"]) is True

    def test_matches_url_too(self) -> None:
        story = Story(
            title="Interesting project",
            url="https://github.com/rust-lang/rust",
            source=SourceType.GITHUB_TRENDING,
        )
        assert story.is_relevant(["rust"]) is True

    def test_empty_topics_never_relevant(self) -> None:
        story = Story(title="Anything", url="https://example.com", source=SourceType.HN_TOP)
        assert story.is_relevant([]) is False


class TestBriefing:
    def test_initial_status_is_pending(self) -> None:
        b = Briefing(user_id="u1", date="2026-03-05", topics=["python"])
        assert b.status == BriefingStatus.PENDING

    def test_mark_ready_sets_status_and_content(self) -> None:
        b = Briefing(user_id="u1", date="2026-03-05", topics=["python"])
        b.mark_ready("# Today's digest\n\nStuff happened.")
        assert b.status == BriefingStatus.READY
        assert "Today's digest" in b.digest_markdown
        assert b.generated_at is not None

    def test_story_count(self) -> None:
        b = Briefing(user_id="u1", date="2026-03-05", topics=["python"])
        b.stories = [
            Story(title="A", url="https://a.com", source=SourceType.HN_TOP),
            Story(title="B", url="https://b.com", source=SourceType.HN_TOP),
        ]
        assert b.story_count() == 2

    def test_credits_consumed_default_one(self) -> None:
        b = Briefing(user_id="u1", date="2026-03-05", topics=["python"])
        assert b.credits_consumed == 1


class TestUserConfig:
    def test_valid_config(self) -> None:
        cfg = UserConfig(user_id="u1", topics=["python", "llm"])
        assert cfg.delivery_hour_utc == 7
        assert SourceType.HN_TOP in cfg.sources

    def test_invalid_hour_raises(self) -> None:
        with pytest.raises(ValueError, match="delivery_hour_utc"):
            UserConfig(user_id="u1", topics=["python"], delivery_hour_utc=25)

    def test_empty_topics_raises(self) -> None:
        with pytest.raises(ValueError, match="topic"):
            UserConfig(user_id="u1", topics=[])
