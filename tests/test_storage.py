"""Tests for SQLite briefing storage."""

from __future__ import annotations

from pathlib import Path

import pytest

from briefd.models import Briefing, BriefingStatus
from briefd.storage import BriefingStore


@pytest.fixture
def store(tmp_path: Path) -> BriefingStore:
    return BriefingStore(tmp_path / "test.db")


class TestBriefingStore:
    def test_save_and_retrieve(self, store: BriefingStore) -> None:
        b = Briefing(user_id="u1", date="2026-03-05", topics=["python"])
        b.mark_ready("# Digest\n\nContent here.")
        store.save(b)

        retrieved = store.get(user_id="u1", date="2026-03-05")
        assert retrieved is not None
        assert retrieved.user_id == "u1"
        assert retrieved.date == "2026-03-05"
        assert "Digest" in retrieved.digest_markdown
        assert retrieved.status == BriefingStatus.READY

    def test_get_returns_none_when_missing(self, store: BriefingStore) -> None:
        result = store.get(user_id="u1", date="2026-03-05")
        assert result is None

    def test_list_for_user(self, store: BriefingStore) -> None:
        for date in ["2026-03-03", "2026-03-04", "2026-03-05"]:
            b = Briefing(user_id="u1", date=date, topics=["python"])
            b.mark_ready(f"Digest for {date}")
            store.save(b)

        # Different user — should not appear
        other = Briefing(user_id="u2", date="2026-03-05", topics=["rust"])
        other.mark_ready("Other user digest")
        store.save(other)

        results = store.list_for_user("u1")
        assert len(results) == 3
        assert all(r.user_id == "u1" for r in results)

    def test_save_overwrites_existing(self, store: BriefingStore) -> None:
        b = Briefing(user_id="u1", date="2026-03-05", topics=["python"])
        b.mark_ready("First version")
        store.save(b)

        b2 = Briefing(user_id="u1", date="2026-03-05", topics=["python"])
        b2.mark_ready("Updated version")
        store.save(b2)

        retrieved = store.get(user_id="u1", date="2026-03-05")
        assert retrieved is not None
        assert "Updated version" in retrieved.digest_markdown

    def test_db_created_automatically(self, tmp_path: Path) -> None:
        db_path = tmp_path / "nested" / "dir" / "briefd.db"
        store = BriefingStore(db_path)
        assert db_path.exists()
