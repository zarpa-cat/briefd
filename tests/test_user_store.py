"""Tests for UserConfigStore — persists per-user topic/schedule preferences."""

from __future__ import annotations

import tempfile
from pathlib import Path

from briefd.models import UserConfig
from briefd.storage import BriefingStore, UserConfigStore


class TestUserConfigStore:
    def setup_method(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.db = Path(self._td.name) / "test.db"
        self.store = UserConfigStore(self.db)

    def teardown_method(self) -> None:
        self._td.cleanup()

    def test_save_and_get(self) -> None:
        cfg = UserConfig(user_id="alice@x.com", topics=["python", "rust"], delivery_hour_utc=7)
        self.store.save(cfg)
        result = self.store.get("alice@x.com")
        assert result is not None
        assert result.user_id == "alice@x.com"
        assert result.topics == ["python", "rust"]
        assert result.delivery_hour_utc == 7

    def test_get_returns_none_for_unknown_user(self) -> None:
        assert self.store.get("nobody@x.com") is None

    def test_save_updates_existing(self) -> None:
        cfg = UserConfig(user_id="u@x.com", topics=["llm"], delivery_hour_utc=8)
        self.store.save(cfg)
        cfg2 = UserConfig(user_id="u@x.com", topics=["llm", "security"], delivery_hour_utc=9)
        self.store.save(cfg2)
        result = self.store.get("u@x.com")
        assert result is not None
        assert result.topics == ["llm", "security"]
        assert result.delivery_hour_utc == 9

    def test_list_all(self) -> None:
        self.store.save(UserConfig(user_id="a@x.com", topics=["python"]))
        self.store.save(UserConfig(user_id="b@x.com", topics=["rust"]))
        all_cfgs = self.store.list_all()
        assert len(all_cfgs) == 2
        ids = {c.user_id for c in all_cfgs}
        assert ids == {"a@x.com", "b@x.com"}

    def test_list_all_empty(self) -> None:
        assert self.store.list_all() == []

    def test_delete(self) -> None:
        self.store.save(UserConfig(user_id="u@x.com", topics=["python"]))
        self.store.delete("u@x.com")
        assert self.store.get("u@x.com") is None

    def test_delete_nonexistent_is_noop(self) -> None:
        self.store.delete("nobody@x.com")  # should not raise

    def test_shared_db_with_briefing_store(self) -> None:
        """Both stores can share the same SQLite file safely."""
        briefing_store = BriefingStore(self.db)
        cfg = UserConfig(user_id="u@x.com", topics=["python"])
        self.store.save(cfg)
        assert briefing_store.get("u@x.com", "2026-03-06") is None  # no briefing, no crash
        assert self.store.get("u@x.com") is not None
