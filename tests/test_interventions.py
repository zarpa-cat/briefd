"""Tests for agent-driven intervention flows."""

from __future__ import annotations

from briefd.interventions import (
    InterventionResult,
    InterventionStatus,
    build_churn_email,
    build_trial_nudge_email,
    should_send_trial_nudge,
)
from briefd.models import Briefing, UserConfig


def _cfg(user_id: str = "u1", topics: list[str] | None = None) -> UserConfig:
    return UserConfig(user_id=user_id, topics=topics or ["python"])


def _ready_briefing(user_id: str = "u1") -> Briefing:
    b = Briefing(user_id=user_id, date="2026-03-04", topics=["python"])
    b.mark_ready("# Digest")
    return b


class TestChurnEmail:
    def test_churn_email_contains_user_id(self) -> None:
        email = build_churn_email(user_id="alice@x.com", topics=["python", "rust"])
        assert "alice@x.com" in email["to"]
        assert "python" in email["body"].lower() or "digest" in email["body"].lower()

    def test_churn_email_has_required_fields(self) -> None:
        email = build_churn_email(user_id="u@x.com", topics=["llm"])
        assert "to" in email
        assert "subject" in email
        assert "body" in email
        assert email["to"] == "u@x.com"


class TestTrialNudge:
    def test_nudge_when_two_briefings_read(self) -> None:
        briefings = [_ready_briefing("u1"), _ready_briefing("u1")]
        assert should_send_trial_nudge(briefings, days_since_signup=3) is True

    def test_no_nudge_before_day_3(self) -> None:
        briefings = [_ready_briefing("u1"), _ready_briefing("u1")]
        assert should_send_trial_nudge(briefings, days_since_signup=2) is False

    def test_no_nudge_if_fewer_than_two_briefings(self) -> None:
        briefings = [_ready_briefing("u1")]
        assert should_send_trial_nudge(briefings, days_since_signup=3) is False

    def test_trial_nudge_email_structure(self) -> None:
        email = build_trial_nudge_email(user_id="u@x.com", topics=["python"])
        assert email["to"] == "u@x.com"
        assert "subject" in email
        assert "body" in email


class TestInterventionResult:
    def test_result_tracks_status(self) -> None:
        r = InterventionResult(
            user_id="u1",
            intervention_type="churn",
            status=InterventionStatus.DRAFTED,
            message="Email drafted for review",
        )
        assert r.status == InterventionStatus.DRAFTED
        assert r.user_id == "u1"
