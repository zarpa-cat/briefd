"""Briefd CLI — run a briefing from the command line."""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown

from briefd.fetcher import fetch_github_trending, fetch_hn_top
from briefd.models import BriefingStatus, UserConfig
from briefd.pipeline import generate_briefing
from briefd.storage import BriefingStore

console = Console()


@click.group()
def cli() -> None:
    """Briefd — daily AI technical digest."""


@cli.command()
@click.option(
    "--topics",
    required=True,
    help="Comma-separated topics to track (e.g. python,rust,llm)",
)
@click.option("--limit", default=20, show_default=True, help="Max stories to fetch per source")
@click.option("--date", default=None, help="Date for the briefing (default: today, YYYY-MM-DD)")
@click.option("--no-github", is_flag=True, default=False, help="Skip GitHub Trending")
@click.option("--save", is_flag=True, default=False, help="Save briefing to local DB")
@click.option("--db", default="briefd.db", show_default=True, help="Path to SQLite DB")
def run(topics: str, limit: int, date: str | None, no_github: bool, save: bool, db: str) -> None:
    """Fetch stories and generate today's briefing."""
    topic_list = [t.strip() for t in topics.split(",") if t.strip()]
    if not topic_list:
        raise click.UsageError("At least one topic required")

    briefing_date = date or datetime.now(UTC).strftime("%Y-%m-%d")
    cfg = UserConfig(user_id="local", topics=topic_list, max_stories=limit)

    asyncio.run(_run_async(cfg, briefing_date, no_github, save=save, db_path=db))


async def _run_async(
    cfg: UserConfig,
    date: str,
    no_github: bool,
    save: bool = False,
    db_path: str = "briefd.db",
) -> None:
    with console.status("[bold blue]Fetching stories…"):
        hn_stories = await fetch_hn_top(limit=cfg.max_stories * 2)
        gh_stories = [] if no_github else await fetch_github_trending(limit=20)

    all_stories = hn_stories + gh_stories
    console.print(f"  [dim]Fetched {len(all_stories)} stories from {2 - no_github} sources[/dim]")

    with console.status("[bold blue]Generating digest…"):
        briefing = await generate_briefing(cfg, all_stories, date=date)

    if briefing.status == BriefingStatus.FAILED:
        console.print("[bold red]✗ Briefing generation failed.[/bold red]")
        console.print("[dim]Check that ANTHROPIC_API_KEY is set.[/dim]")
        sys.exit(1)

    console.print()
    console.print(Markdown(briefing.digest_markdown))
    console.print()
    console.print(f"[dim]Briefd · {date} · {briefing.story_count()} stories · {cfg.topics}[/dim]")

    if save:
        store = BriefingStore(Path(db_path))
        store.save(briefing)
        console.print(f"[dim]Saved to {db_path}[/dim]")


@cli.command()
@click.option("--db", default="briefd.db", show_default=True, help="Path to SQLite DB")
@click.option("--hour", default=None, type=int, help="Override current UTC hour (for testing)")
@click.option("--date", default=None, help="Override date (YYYY-MM-DD, for testing)")
@click.option(
    "--user",
    "users",
    multiple=True,
    help="user_id:topics:hour triples, e.g. alice@x.com:python,rust:7",
)
def schedule(db: str, hour: int | None, date: str | None, users: tuple[str, ...]) -> None:
    """Run the scheduler — generate briefings for all due users.

    Example:
        briefd schedule --user alice@x.com:python,rust:7 --user bob@x.com:llm:8
    """
    import asyncio

    from briefd.models import UserConfig
    from briefd.scheduler import UserJob, run_scheduler

    jobs: list[UserJob] = []
    for spec in users:
        parts = spec.split(":")
        if len(parts) != 3:
            raise click.UsageError(f"Invalid user spec '{spec}' — expected user_id:topics:hour")
        uid, topics_str, hour_str = parts
        try:
            delivery_hour = int(hour_str)
        except ValueError:
            raise click.UsageError(f"Invalid hour'{hour_str}' in spec '{spec}'") from None  # noqa: B904 '{hour_str}' in spec '{spec}'")
        cfg = UserConfig(
            user_id=uid,
            topics=[t.strip() for t in topics_str.split(",") if t.strip()],
            delivery_hour_utc=delivery_hour,
        )
        jobs.append(UserJob(cfg=cfg))

    if not jobs:
        console.print("[yellow]No users configured — nothing to do.[/yellow]")
        return

    async def _run() -> None:
        result = await run_scheduler(
            jobs=jobs,
            db_path=Path(db),
            current_hour_utc=hour,
            date=date,
        )
        console.print(
            f"\n[bold]Scheduler run complete:[/bold] "
            f"attempted={result.attempted} "
            f"succeeded=[green]{result.succeeded}[/green] "
            f"failed=[red]{result.failed}[/red] "
            f"skipped={result.skipped}"
        )
        if result.errors:
            for err in result.errors:
                console.print(f"  [red]✗ {err}[/red]")

    asyncio.run(_run())


@cli.command()
@click.option("--db", default="briefd.db", show_default=True, help="Path to SQLite DB")
@click.option(
    "--user",
    "user_ids",
    multiple=True,
    default=["local"],
    show_default=True,
    help="User IDs to include in health check",
)
@click.option("--out", default=None, help="Write report to file (default: stdout)")
def health(db: str, user_ids: tuple[str, ...], out: str | None) -> None:
    """Generate a health report for all users."""
    from briefd.health import generate_health_report
    from briefd.storage import BriefingStore

    store = BriefingStore(Path(db))
    report = generate_health_report(store=store, user_ids=list(user_ids))
    md = report.to_markdown()

    if out:
        Path(out).write_text(md)
        console.print(f"[dim]Report written to {out}[/dim]")
    else:
        console.print(Markdown(md))

    if report.success_rate < 0.8 and report.total_generated > 0:
        raise SystemExit(1)  # non-zero exit for CI / monitoring


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
