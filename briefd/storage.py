"""SQLite storage for Briefd — persist generated briefings."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from briefd.models import Briefing, BriefingStatus

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS briefings (
    user_id     TEXT NOT NULL,
    date        TEXT NOT NULL,
    topics      TEXT NOT NULL,
    digest      TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'pending',
    credits     INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT,
    PRIMARY KEY (user_id, date)
)
"""


class BriefingStore:
    """Simple SQLite-backed store for user briefings."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(CREATE_TABLE)

    def save(self, briefing: Briefing) -> None:
        """Insert or replace a briefing."""
        generated_at = (
            briefing.generated_at.isoformat() if briefing.generated_at else None
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO briefings
                    (user_id, date, topics, digest, status, credits, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    briefing.user_id,
                    briefing.date,
                    json.dumps(briefing.topics),
                    briefing.digest_markdown,
                    briefing.status.value,
                    briefing.credits_consumed,
                    generated_at,
                ),
            )

    def get(self, user_id: str, date: str) -> Briefing | None:
        """Retrieve a specific briefing by user and date."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM briefings WHERE user_id = ? AND date = ?",
                (user_id, date),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_briefing(row)

    def list_for_user(self, user_id: str, limit: int = 30) -> list[Briefing]:
        """List recent briefings for a user, newest first."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM briefings WHERE user_id = ? ORDER BY date DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [self._row_to_briefing(r) for r in rows]

    @staticmethod
    def _row_to_briefing(row: sqlite3.Row) -> Briefing:
        b = Briefing(
            user_id=row["user_id"],
            date=row["date"],
            topics=json.loads(row["topics"]),
            digest_markdown=row["digest"],
            status=BriefingStatus(row["status"]),
            credits_consumed=row["credits"],
        )
        return b
