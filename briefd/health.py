"""Health monitoring for Briefd — agent reads this to understand system state.

The agent generates a daily health report and writes it to a known path.
On each work cycle, the agent can read this report to decide if intervention
is needed (e.g. high failure rate, drop in generation count).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from briefd.models import BriefingStatus
from briefd.storage import BriefingStore


@dataclass
class HealthReport:
    date: str
    user_count: int
    total_generated: int
    succeeded: int
    failed: int
    notes: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total_generated == 0:
            return 0.0
        return self.succeeded / self.total_generated

    def to_markdown(self) -> str:
        rate_pct = f"{self.success_rate * 100:.0f}%"
        status = "✓" if self.success_rate >= 0.9 else "⚠" if self.success_rate >= 0.5 else "✗"
        lines = [
            f"# Briefd Health Report — {self.date}",
            "",
            f"**Status:** {status}  ",
            f"**Users:** {self.user_count}  ",
            f"**Briefings generated:** {self.total_generated}  ",
            f"**Succeeded:** {self.succeeded} ({rate_pct})  ",
            f"**Failed:** {self.failed}  ",
        ]
        if self.notes:
            lines += ["", "## Notes", ""]
            lines += [f"- {n}" for n in self.notes]
        return "\n".join(lines)


def generate_health_report(
    store: BriefingStore,
    user_ids: list[str],
    date: str | None = None,
) -> HealthReport:
    """Generate a health report by scanning recent briefings for all users."""
    today = date or datetime.now(UTC).strftime("%Y-%m-%d")
    total = succeeded = failed = 0
    notes: list[str] = []

    for user_id in user_ids:
        briefings = store.list_for_user(user_id, limit=7)  # last 7 days
        for b in briefings:
            total += 1
            if b.status == BriefingStatus.READY:
                succeeded += 1
            elif b.status == BriefingStatus.FAILED:
                failed += 1

    report = HealthReport(
        date=today,
        user_count=len(user_ids),
        total_generated=total,
        succeeded=succeeded,
        failed=failed,
    )

    if report.success_rate < 0.8 and total > 0:
        notes.append(f"Success rate {report.success_rate:.0%} below 80% threshold — check LLM API")
    if failed > 0:
        notes.append(f"{failed} briefing(s) failed in last 7 days per user")

    report.notes = notes
    return report
