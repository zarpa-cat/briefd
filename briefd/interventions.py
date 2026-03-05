"""Agent-driven intervention flows for Briefd.

The agent watches for events (via webhooks + scheduled checks) and
autonomously drafts interventions. Key principle: the agent drafts,
logs, and (in Phase 5) sends — but never sends unseen email silently.

Current interventions:
- ChurnIntervention: cancellation detected → draft win-back email
- TrialNudge: trial user with 2+ briefings read on day 3 → upgrade prompt
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from briefd.models import Briefing

logger = logging.getLogger(__name__)


class InterventionStatus(Enum):
    DRAFTED = "drafted"  # email built, not yet sent
    SENT = "sent"  # email delivered
    SKIPPED = "skipped"  # conditions not met, intervention not warranted
    FAILED = "failed"  # error during intervention


@dataclass
class InterventionResult:
    user_id: str
    intervention_type: str
    status: InterventionStatus
    message: str = ""


@dataclass
class ChurnIntervention:
    user_id: str
    topics: list[str]
    cancelled_product: str = ""


@dataclass
class TrialNudge:
    user_id: str
    topics: list[str]
    briefings_read: int = 0


def build_churn_email(user_id: str, topics: list[str]) -> dict:
    """Build a win-back email for a recently cancelled subscriber.

    The agent drafts this; a human (or future autonomous send) delivers it.
    """
    topic_str = ", ".join(topics) if topics else "your topics"
    return {
        "to": user_id,
        "subject": "We'll miss your morning digest 🐾",
        "body": (
            f"Hey,\n\n"
            f"Your Briefd subscription for {topic_str} has been cancelled.\n\n"
            f"If there's anything we could do better — different topics, "
            f"fewer emails, a different format — we'd genuinely like to know.\n\n"
            f"If you'd like to come back, your digest history is still here:\n"
            f"https://briefd.app/briefings\n\n"
            f"— Briefd 🐾"
        ),
    }


def build_trial_nudge_email(user_id: str, topics: list[str]) -> dict:
    """Build a trial conversion nudge for an engaged trial user."""
    topic_str = ", ".join(topics) if topics else "your topics"
    return {
        "to": user_id,
        "subject": "You've read 2 briefings — enjoying it?",
        "body": (
            f"Hey,\n\n"
            f"You've been getting your daily {topic_str} digest for a few days now. "
            f"We hope it's saving you some scrolling.\n\n"
            f"Your trial is still running — if Briefd is useful, "
            f"upgrading keeps the briefings coming after your trial ends:\n"
            f"https://briefd.app/account\n\n"
            f"— Briefd 🐾"
        ),
    }


def should_send_trial_nudge(
    briefings: list[Briefing],
    days_since_signup: int,
    min_briefings: int = 2,
    nudge_day: int = 3,
) -> bool:
    """Return True if this trial user should receive a conversion nudge.

    Conditions:
    - At least `nudge_day` days since signup (default: day 3)
    - At least `min_briefings` briefings successfully generated (proxy for engagement)
    """
    if days_since_signup < nudge_day:
        return False
    ready_count = sum(1 for b in briefings if b.status.value == "ready")
    return ready_count >= min_briefings


async def run_churn_intervention(intervention: ChurnIntervention) -> InterventionResult:
    """Draft a win-back email for a churned user. Logs it; does not send."""
    email = build_churn_email(
        user_id=intervention.user_id,
        topics=intervention.topics,
    )
    # Phase 5: call send_email(email) here once autonomous send is approved
    logger.info(
        "Churn intervention drafted for %s: subject=%r",
        intervention.user_id,
        email["subject"],
    )
    return InterventionResult(
        user_id=intervention.user_id,
        intervention_type="churn",
        status=InterventionStatus.DRAFTED,
        message=f"Win-back email drafted for {intervention.user_id}",
    )


async def run_trial_nudge(nudge: TrialNudge) -> InterventionResult:
    """Draft a trial conversion nudge. Logs it; does not send."""
    email = build_trial_nudge_email(
        user_id=nudge.user_id,
        topics=nudge.topics,
    )
    logger.info(
        "Trial nudge drafted for %s (read %d briefings): subject=%r",
        nudge.user_id,
        nudge.briefings_read,
        email["subject"],
    )
    return InterventionResult(
        user_id=nudge.user_id,
        intervention_type="trial_nudge",
        status=InterventionStatus.DRAFTED,
        message=f"Trial nudge drafted for {nudge.user_id}",
    )
