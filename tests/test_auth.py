"""Tests for magic link authentication."""

from __future__ import annotations

from pathlib import Path

import pytest

from briefd.auth import AuthStore, TokenStatus, generate_token, verify_token


class TestAuthStore:
    @pytest.fixture
    def store(self, tmp_path: Path) -> AuthStore:
        return AuthStore(tmp_path / "auth.db")

    def test_store_and_retrieve_token(self, store: AuthStore) -> None:
        token = generate_token()
        store.save_token(token, email="user@example.com")
        result = store.get_token(token)
        assert result is not None
        assert result["email"] == "user@example.com"
        assert result["used"] is False

    def test_unknown_token_returns_none(self, store: AuthStore) -> None:
        assert store.get_token("nonexistent") is None

    def test_mark_used(self, store: AuthStore) -> None:
        token = generate_token()
        store.save_token(token, email="user@example.com")
        store.mark_used(token)
        result = store.get_token(token)
        assert result is not None
        assert result["used"] is True

    def test_db_created_automatically(self, tmp_path: Path) -> None:
        db = tmp_path / "nested" / "auth.db"
        _ = AuthStore(db)
        assert db.exists()


class TestTokenGeneration:
    def test_tokens_are_unique(self) -> None:
        tokens = {generate_token() for _ in range(100)}
        assert len(tokens) == 100

    def test_token_is_url_safe(self) -> None:
        token = generate_token()
        assert " " not in token
        assert "/" not in token or token.count("/") == 0


class TestVerifyToken:
    @pytest.fixture
    def store(self, tmp_path: Path) -> AuthStore:
        return AuthStore(tmp_path / "auth.db")

    def test_valid_token_returns_email(self, store: AuthStore) -> None:
        token = generate_token()
        store.save_token(token, email="user@example.com")
        status, email = verify_token(store, token)
        assert status == TokenStatus.VALID
        assert email == "user@example.com"

    def test_valid_token_is_marked_used(self, store: AuthStore) -> None:
        token = generate_token()
        store.save_token(token, email="user@example.com")
        verify_token(store, token)
        assert store.get_token(token)["used"] is True

    def test_used_token_returns_already_used(self, store: AuthStore) -> None:
        token = generate_token()
        store.save_token(token, email="user@example.com")
        verify_token(store, token)
        status, _ = verify_token(store, token)
        assert status == TokenStatus.ALREADY_USED

    def test_unknown_token_returns_invalid(self, store: AuthStore) -> None:
        status, _ = verify_token(store, "badtoken")
        assert status == TokenStatus.INVALID
