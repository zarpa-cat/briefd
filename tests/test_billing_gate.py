"""Tests for billing gate integration in the pipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from briefd.billing import CustomerStatus
from briefd.models import Briefing, BriefingStatus, SourceType, Story, UserConfig
from briefd.pipeline import generate_briefing_gated


def _stories() -> list[Story]:
    return [Story(title="Python news", url="https://python.org", source=SourceType.HN_TOP)]


def _cfg() -> UserConfig:
    return UserConfig(user_id="u1", topics=["python"])


def _active_status() -> CustomerStatus:
    return CustomerStatus(customer_id="u1", has_premium=True, credit_balance=0)


def _no_access_status() -> CustomerStatus:
    return CustomerStatus(customer_id="u1", has_premium=False, credit_balance=0)


class TestGenerateBriefingGated:
    async def test_generates_when_premium(self) -> None:
        ready = Briefing(user_id="u1", date="2026-03-05", topics=["python"])
        ready.mark_ready("# Digest")

        with (
            patch("briefd.pipeline.call_llm", new_callable=AsyncMock, return_value="# Digest"),
        ):
            briefing = await generate_briefing_gated(
                cfg=_cfg(),
                stories=_stories(),
                date="2026-03-05",
                customer_status=_active_status(),
            )

        assert briefing.status == BriefingStatus.READY

    async def test_generates_when_has_credits(self) -> None:
        credits_status = CustomerStatus(customer_id="u1", has_premium=False, credit_balance=3)

        with patch("briefd.pipeline.call_llm", new_callable=AsyncMock, return_value="# Digest"):
            briefing = await generate_briefing_gated(
                cfg=_cfg(),
                stories=_stories(),
                date="2026-03-05",
                customer_status=credits_status,
            )

        assert briefing.status == BriefingStatus.READY

    async def test_blocked_without_access(self) -> None:
        briefing = await generate_briefing_gated(
            cfg=_cfg(),
            stories=_stories(),
            date="2026-03-05",
            customer_status=_no_access_status(),
        )

        assert briefing.status == BriefingStatus.FAILED
        assert "access" in briefing.digest_markdown.lower() or briefing.digest_markdown == ""

    async def test_no_llm_call_when_blocked(self) -> None:
        with patch("briefd.pipeline.call_llm", new_callable=AsyncMock) as mock_llm:
            await generate_briefing_gated(
                cfg=_cfg(),
                stories=_stories(),
                date="2026-03-05",
                customer_status=_no_access_status(),
            )
        mock_llm.assert_not_called()
