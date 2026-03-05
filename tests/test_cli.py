"""Tests for the Briefd CLI."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from briefd.cli import cli
from briefd.models import Briefing, BriefingStatus, SourceType, Story


def _ready_briefing(user_id: str = "local") -> Briefing:
    b = Briefing(user_id=user_id, date="2026-03-05", topics=["python"])
    b.mark_ready("# Today in Python\n\nSomething interesting happened.")
    return b


def _stories() -> list[Story]:
    return [
        Story(
            title="Python 3.14 ships",
            url="https://python.org",
            source=SourceType.HN_TOP,
            score=300,
        ),
    ]


class TestCLIRun:
    def test_run_outputs_briefing(self) -> None:
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
        assert "Today in Python" in result.output

    def test_run_shows_error_on_failed_briefing(self) -> None:
        runner = CliRunner()
        failed = Briefing(user_id="local", date="2026-03-05", topics=["python"])
        failed.status = BriefingStatus.FAILED
        with (
            patch("briefd.cli.fetch_hn_top", new_callable=AsyncMock, return_value=[]),
            patch("briefd.cli.fetch_github_trending", new_callable=AsyncMock, return_value=[]),
            patch("briefd.cli.generate_briefing", new_callable=AsyncMock, return_value=failed),
        ):
            result = runner.invoke(cli, ["run", "--topics", "python"])
        assert result.exit_code != 0

    def test_run_requires_topics(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["run"])
        assert result.exit_code != 0

    def test_run_accepts_multiple_topics(self) -> None:
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
            result = runner.invoke(cli, ["run", "--topics", "python,rust,llm"])
        assert result.exit_code == 0
