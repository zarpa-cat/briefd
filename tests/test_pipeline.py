"""Tests for the briefing pipeline — filter and summarise."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from briefd.models import BriefingStatus, SourceType, Story, UserConfig
from briefd.pipeline import filter_stories, generate_briefing


class TestFilterStories:
    def _story(self, title: str, url: str = "https://x.com") -> Story:
        return Story(title=title, url=url, source=SourceType.HN_TOP)

    def test_keeps_matching_stories(self) -> None:
        stories = [
            self._story("Python 3.14 is out"),
            self._story("Football results"),
            self._story("Rust async deep dive"),
        ]
        cfg = UserConfig(user_id="u1", topics=["python", "rust"])
        result = filter_stories(stories, cfg)
        assert len(result) == 2
        titles = {s.title for s in result}
        assert "Python 3.14 is out" in titles
        assert "Rust async deep dive" in titles

    def test_respects_max_stories(self) -> None:
        stories = [self._story(f"Python story {i}") for i in range(20)]
        cfg = UserConfig(user_id="u1", topics=["python"], max_stories=5)
        result = filter_stories(stories, cfg)
        assert len(result) == 5

    def test_empty_stories_returns_empty(self) -> None:
        cfg = UserConfig(user_id="u1", topics=["python"])
        assert filter_stories([], cfg) == []

    def test_no_matches_returns_empty(self) -> None:
        stories = [self._story("Sports news"), self._story("Celebrity gossip")]
        cfg = UserConfig(user_id="u1", topics=["python"])
        assert filter_stories(stories, cfg) == []


class TestGenerateBriefing:
    async def test_returns_ready_briefing_on_success(self) -> None:
        cfg = UserConfig(user_id="u1", topics=["python"])
        stories = [
            Story(title="Python tip", url="https://python.org", source=SourceType.HN_TOP, score=200),
        ]

        with patch("briefd.pipeline.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "# Today in Python\n\nPython tip was trending."
            briefing = await generate_briefing(cfg, stories, date="2026-03-05")

        assert briefing.status == BriefingStatus.READY
        assert "Python tip" in briefing.digest_markdown
        assert briefing.date == "2026-03-05"
        assert briefing.user_id == "u1"

    async def test_marks_failed_on_llm_error(self) -> None:
        cfg = UserConfig(user_id="u1", topics=["python"])
        stories = [
            Story(title="Python tip", url="https://python.org", source=SourceType.HN_TOP),
        ]

        with patch("briefd.pipeline.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("LLM unavailable")
            briefing = await generate_briefing(cfg, stories, date="2026-03-05")

        assert briefing.status == BriefingStatus.FAILED

    async def test_empty_stories_still_generates(self) -> None:
        cfg = UserConfig(user_id="u1", topics=["python"])
        with patch("briefd.pipeline.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "# Quiet day\n\nNothing matched today."
            briefing = await generate_briefing(cfg, [], date="2026-03-05")

        assert briefing.status == BriefingStatus.READY
