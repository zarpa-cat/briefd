"""Tests for the health monitoring report."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from briefd.health import generate_health_report
from briefd.models import Briefing, BriefingStatus


def _briefing(status: str, date: str = "2026-03-05") -> Briefing:
    b = Briefing(user_id="u1", date=date, topics=["python"])
    b.status = BriefingStatus(status)
    if status == "ready":
        b.digest_markdown = "# Digest"
    return b


class TestHealthReport:
    def test_report_counts_ready_and_failed(self, tmp_path: Path) -> None:
        mock_store = MagicMock()
        mock_store.list_for_user.return_value = [
            _briefing("ready", "2026-03-05"),
            _briefing("ready", "2026-03-04"),
            _briefing("failed", "2026-03-03"),
        ]

        report = generate_health_report(
            store=mock_store,
            user_ids=["u1"],
            date="2026-03-05",
        )

        assert report.total_generated == 3
        assert report.succeeded == 2
        assert report.failed == 1

    def test_report_calculates_success_rate(self, tmp_path: Path) -> None:
        mock_store = MagicMock()
        mock_store.list_for_user.return_value = [
            _briefing("ready"),
            _briefing("ready"),
            _briefing("ready"),
            _briefing("failed"),
        ]

        report = generate_health_report(
            store=mock_store,
            user_ids=["u1"],
            date="2026-03-05",
        )

        assert report.success_rate == 0.75

    def test_report_to_markdown(self, tmp_path: Path) -> None:
        mock_store = MagicMock()
        mock_store.list_for_user.return_value = [_briefing("ready")]

        report = generate_health_report(
            store=mock_store,
            user_ids=["u1"],
            date="2026-03-05",
        )

        md = report.to_markdown()
        assert "2026-03-05" in md
        assert "success" in md.lower() or "✓" in md

    def test_empty_store_gives_zero_report(self) -> None:
        mock_store = MagicMock()
        mock_store.list_for_user.return_value = []

        report = generate_health_report(
            store=mock_store,
            user_ids=["u1"],
            date="2026-03-05",
        )

        assert report.total_generated == 0
        assert report.success_rate == 0.0
