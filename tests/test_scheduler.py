"""Tests for the agent scheduler — daily briefing generation for all users."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from briefd.models import Briefing, BriefingStatus, SourceType, Story, UserConfig
from briefd.scheduler import UserJob, is_due, run_scheduler


def _ready_briefing(user_id: str = "u1") -> Briefing:
    b = Briefing(user_id=user_id, date="2026-03-05", topics=["python"])
    b.mark_ready("# Digest")
    return b


def _stories() -> list[Story]:
    return [Story(title="Python news", url="https://python.org", source=SourceType.HN_TOP)]


class TestIsDue:
    def test_due_when_current_hour_matches(self) -> None:
        cfg = UserConfig(user_id="u1", topics=["python"], delivery_hour_utc=7)
        assert is_due(cfg, current_hour_utc=7) is True

    def test_not_due_when_hour_differs(self) -> None:
        cfg = UserConfig(user_id="u1", topics=["python"], delivery_hour_utc=7)
        assert is_due(cfg, current_hour_utc=8) is False

    def test_not_due_if_already_generated_today(self) -> None:
        cfg = UserConfig(user_id="u1", topics=["python"], delivery_hour_utc=7)
        assert is_due(cfg, current_hour_utc=7, already_generated_today=True) is False


class TestRunScheduler:
    async def test_generates_briefing_for_due_users(self) -> None:
        jobs = [
            UserJob(cfg=UserConfig(user_id="u1", topics=["python"], delivery_hour_utc=7)),
            UserJob(cfg=UserConfig(user_id="u2", topics=["rust"], delivery_hour_utc=9)),
        ]

        with (
            patch("briefd.scheduler.fetch_hn_top", new_callable=AsyncMock, return_value=_stories()),
            patch(
                "briefd.scheduler.fetch_github_trending", new_callable=AsyncMock, return_value=[]
            ),
            patch("briefd.scheduler.generate_briefing", new_callable=AsyncMock) as mock_gen,
            patch("briefd.scheduler.BriefingStore") as mock_store_cls,
        ):
            mock_gen.return_value = _ready_briefing("u1")
            mock_store = MagicMock()
            mock_store.get.return_value = None  # not already generated
            mock_store_cls.return_value = mock_store

            result = await run_scheduler(
                jobs=jobs,
                current_hour_utc=7,
                date="2026-03-05",
                db_path=Path("test.db"),
            )

        # Only u1 is due at hour 7
        assert result.attempted == 1
        assert result.succeeded == 1
        assert result.failed == 0

    async def test_skips_already_generated(self) -> None:
        jobs = [
            UserJob(cfg=UserConfig(user_id="u1", topics=["python"], delivery_hour_utc=7)),
        ]

        with (
            patch("briefd.scheduler.fetch_hn_top", new_callable=AsyncMock, return_value=_stories()),
            patch(
                "briefd.scheduler.fetch_github_trending", new_callable=AsyncMock, return_value=[]
            ),
            patch("briefd.scheduler.generate_briefing", new_callable=AsyncMock) as mock_gen,
            patch("briefd.scheduler.BriefingStore") as mock_store_cls,
        ):
            mock_store = MagicMock()
            mock_store.get.return_value = _ready_briefing("u1")  # already done
            mock_store_cls.return_value = mock_store

            result = await run_scheduler(
                jobs=jobs,
                current_hour_utc=7,
                date="2026-03-05",
                db_path=Path("test.db"),
            )

        mock_gen.assert_not_called()
        assert result.attempted == 0

    async def test_counts_failures(self) -> None:
        jobs = [
            UserJob(cfg=UserConfig(user_id="u1", topics=["python"], delivery_hour_utc=7)),
        ]
        failed = Briefing(user_id="u1", date="2026-03-05", topics=["python"])
        failed.status = BriefingStatus.FAILED

        with (
            patch("briefd.scheduler.fetch_hn_top", new_callable=AsyncMock, return_value=_stories()),
            patch(
                "briefd.scheduler.fetch_github_trending", new_callable=AsyncMock, return_value=[]
            ),
            patch(
                "briefd.scheduler.generate_briefing", new_callable=AsyncMock, return_value=failed
            ),
            patch("briefd.scheduler.BriefingStore") as mock_store_cls,
        ):
            mock_store = MagicMock()
            mock_store.get.return_value = None
            mock_store_cls.return_value = mock_store

            result = await run_scheduler(
                jobs=jobs,
                current_hour_utc=7,
                date="2026-03-05",
                db_path=Path("test.db"),
            )

        assert result.attempted == 1
        assert result.failed == 1
        assert result.succeeded == 0
