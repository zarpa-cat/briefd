"""Agent scheduler — autonomous daily briefing generation for all users.

This is the core of "agent-operated": run on a schedule (e.g. every hour),
check which users are due for a briefing, generate and persist them.

The agent operates this loop. No human triggers required.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from briefd.fetcher import fetch_github_trending, fetch_hn_top
from briefd.models import BriefingStatus, UserConfig
from briefd.pipeline import generate_briefing
from briefd.storage import BriefingStore

logger = logging.getLogger(__name__)


@dataclass
class UserJob:
    """A scheduled briefing job for one user."""

    cfg: UserConfig


@dataclass
class SchedulerRun:
    """Summary of one scheduler execution."""

    date: str
    hour_utc: int
    attempted: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def log_summary(self) -> None:
        logger.info(
            "Scheduler run %s@%02dh — attempted=%d succeeded=%d failed=%d skipped=%d",
            self.date,
            self.hour_utc,
            self.attempted,
            self.succeeded,
            self.failed,
            self.skipped,
        )


def is_due(
    cfg: UserConfig,
    current_hour_utc: int,
    already_generated_today: bool = False,
) -> bool:
    """Return True if this user's briefing should be generated right now."""
    if already_generated_today:
        return False
    return cfg.delivery_hour_utc == current_hour_utc


async def run_scheduler(
    jobs: list[UserJob],
    db_path: Path,
    current_hour_utc: int | None = None,
    date: str | None = None,
) -> SchedulerRun:
    """Run the scheduler for all registered users.

    For each user, checks if a briefing is due (matching delivery hour, not
    already generated today). If due: fetch stories, generate, persist.

    Returns a SchedulerRun summary for logging and monitoring.
    """
    now = datetime.now(UTC)
    hour = current_hour_utc if current_hour_utc is not None else now.hour
    today = date or now.strftime("%Y-%m-%d")

    run = SchedulerRun(date=today, hour_utc=hour)
    store = BriefingStore(db_path)

    for job in jobs:
        cfg = job.cfg
        existing = store.get(user_id=cfg.user_id, date=today)
        already_done = existing is not None and existing.status == BriefingStatus.READY

        if not is_due(cfg, current_hour_utc=hour, already_generated_today=already_done):
            run.skipped += 1
            continue

        run.attempted += 1
        logger.info("Generating briefing: user=%s date=%s", cfg.user_id, today)

        try:
            hn_stories = await fetch_hn_top(limit=cfg.max_stories * 2)
            gh_stories = await fetch_github_trending(limit=20)
            all_stories = hn_stories + gh_stories

            briefing = await generate_briefing(cfg, all_stories, date=today)
            store.save(briefing)

            if briefing.status == BriefingStatus.READY:
                run.succeeded += 1
                logger.info("Briefing ready: user=%s", cfg.user_id)
            else:
                run.failed += 1
                logger.warning("Briefing failed: user=%s", cfg.user_id)

        except Exception as exc:
            run.failed += 1
            msg = f"{cfg.user_id}: {exc}"
            run.errors.append(msg)
            logger.error("Scheduler error: %s", msg)

    run.log_summary()
    return run
