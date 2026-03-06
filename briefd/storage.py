"""SQLite storage for Briefd — persist generated briefings and user configs."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from briefd.models import Briefing, BriefingStatus, UserConfig

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
        generated_at = briefing.generated_at.isoformat() if briefing.generated_at else None
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


CREATE_USER_CONFIG_TABLE = """
CREATE TABLE IF NOT EXISTS user_configs (
    user_id          TEXT PRIMARY KEY,
    topics           TEXT NOT NULL DEFAULT '[]',
    delivery_hour    INTEGER NOT NULL DEFAULT 7,
    max_stories      INTEGER NOT NULL DEFAULT 10,
    updated_at       TEXT
)
"""


class UserConfigStore:
    """SQLite-backed store for per-user topic and schedule configuration.

    Can share a database file with BriefingStore — each store manages its own table.
    """

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
            conn.execute(CREATE_USER_CONFIG_TABLE)

    def save(self, cfg: UserConfig) -> None:
        """Insert or update a user's configuration."""
        from datetime import UTC, datetime

        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO user_configs
                    (user_id, topics, delivery_hour, max_stories, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    cfg.user_id,
                    json.dumps(cfg.topics),
                    cfg.delivery_hour_utc,
                    cfg.max_stories,
                    datetime.now(UTC).isoformat(),
                ),
            )

    def get(self, user_id: str) -> UserConfig | None:
        """Return config for a user, or None if not registered."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM user_configs WHERE user_id = ?", (user_id,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_config(row)

    def list_all(self) -> list[UserConfig]:
        """Return all registered user configs."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM user_configs ORDER BY user_id").fetchall()
        return [self._row_to_config(r) for r in rows]

    def delete(self, user_id: str) -> None:
        """Remove a user's config (does not delete their briefings)."""
        with self._connect() as conn:
            conn.execute("DELETE FROM user_configs WHERE user_id = ?", (user_id,))

    @staticmethod
    def _row_to_config(row: sqlite3.Row) -> UserConfig:
        return UserConfig(
            user_id=row["user_id"],
            topics=json.loads(row["topics"]),
            delivery_hour_utc=row["delivery_hour"],
            max_stories=row["max_stories"],
        )
