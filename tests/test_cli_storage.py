"""Tests for CLI --save flag (persist briefings to DB)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from briefd.cli import cli
from briefd.models import Briefing, BriefingStatus, SourceType, Story


def _ready_briefing() -> Briefing:
    b = Briefing(user_id="local", date="2026-03-05", topics=["python"])
    b.mark_ready("# Today\n\nSomething happened.")
    return b


def _stories() -> list[Story]:
    return [Story(title="Python news", url="https://python.org", source=SourceType.HN_TOP)]


class TestCLISave:
    def test_save_flag_persists_briefing(self, tmp_path: Path) -> None:
        db = tmp_path / "briefd.db"
        runner = CliRunner()

        with (
            patch("briefd.cli.fetch_hn_top", new_callable=AsyncMock, return_value=_stories()),
            patch("briefd.cli.fetch_github_trending", new_callable=AsyncMock, return_value=[]),
            patch(
                "briefd.cli.generate_briefing",
                new_callable=AsyncMock,
                return_value=_ready_briefing(),
            ),
        ):
            result = runner.invoke(
                cli,
                ["run", "--topics", "python", "--save", "--db", str(db)],
            )

        assert result.exit_code == 0
        assert db.exists()

        # Verify it was saved
        from briefd.storage import BriefingStore

        store = BriefingStore(db)
        saved = store.get(user_id="local", date="2026-03-05")
        assert saved is not None
        assert saved.status == BriefingStatus.READY

    def test_no_save_flag_does_not_create_db(self, tmp_path: Path) -> None:
        db = tmp_path / "briefd.db"
        runner = CliRunner()

        with (
            patch("briefd.cli.fetch_hn_top", new_callable=AsyncMock, return_value=_stories()),
            patch("briefd.cli.fetch_github_trending", new_callable=AsyncMock, return_value=[]),
            patch(
                "briefd.cli.generate_briefing",
                new_callable=AsyncMock,
                return_value=_ready_briefing(),
            ),
        ):
            result = runner.invoke(cli, ["run", "--topics", "python"])

        assert result.exit_code == 0
        assert not db.exists()
