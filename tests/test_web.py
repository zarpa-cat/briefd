"""Tests for the FastAPI web application."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from briefd.models import Briefing
from briefd.web.app import app


def _ready_briefing(date: str = "2026-03-05") -> Briefing:
    b = Briefing(user_id="u1", date=date, topics=["python", "rust"])
    b.mark_ready("# Today\n\nSomething happened.")
    return b


class TestRoutes:
    def setup_method(self) -> None:
        self.client = TestClient(app)

    def test_index_returns_200(self) -> None:
        resp = self.client.get("/")
        assert resp.status_code == 200
        assert "Briefd" in resp.text

    def test_health_returns_ok(self) -> None:
        resp = self.client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_briefing_list_empty(self) -> None:
        mock_store = MagicMock()
        mock_store.list_for_user.return_value = []
        with patch("briefd.web.app.get_store", return_value=mock_store):
            resp = self.client.get("/briefings?user_id=u1")
        assert resp.status_code == 200
        assert "No briefings" in resp.text

    def test_briefing_list_shows_entries(self) -> None:
        mock_store = MagicMock()
        mock_store.list_for_user.return_value = [
            _ready_briefing("2026-03-05"),
            _ready_briefing("2026-03-04"),
        ]
        with patch("briefd.web.app.get_store", return_value=mock_store):
            resp = self.client.get("/briefings?user_id=u1")
        assert resp.status_code == 200
        assert "2026-03-05" in resp.text
        assert "2026-03-04" in resp.text

    def test_briefing_detail_found(self) -> None:
        mock_store = MagicMock()
        mock_store.get.return_value = _ready_briefing("2026-03-05")
        with patch("briefd.web.app.get_store", return_value=mock_store):
            resp = self.client.get("/briefings/2026-03-05?user_id=u1")
        assert resp.status_code == 200
        assert "2026-03-05" in resp.text

    def test_briefing_detail_not_found(self) -> None:
        mock_store = MagicMock()
        mock_store.get.return_value = None
        with patch("briefd.web.app.get_store", return_value=mock_store):
            resp = self.client.get("/briefings/2099-01-01?user_id=u1")
        assert resp.status_code == 404

    def test_account_without_rc_config(self) -> None:
        with patch.dict("os.environ", {"RC_API_KEY": "", "RC_PROJECT_ID": ""}):
            resp = self.client.get("/account?user_id=u1")
        assert resp.status_code == 200
        assert "RC_API_KEY" in resp.text

    def test_webhook_endpoint_accepts_post(self) -> None:
        payload = {"event": {"type": "RENEWAL", "app_user_id": "u1", "product_id": "premium"}}
        resp = self.client.post("/webhook/revenuecat", json=payload)
        assert resp.status_code == 200
        assert resp.json()["received"] is True
        assert resp.json()["event_type"] == "RENEWAL"

    def test_login_page_returns_200(self) -> None:
        resp = self.client.get("/auth/login")
        assert resp.status_code == 200
        assert "magic link" in resp.text.lower()

    def test_request_magic_link_redirects_to_check_email(self) -> None:
        with patch("briefd.web.app.send_magic_link", new_callable=AsyncMock):
            resp = self.client.post(
                "/auth/request",
                data={"email": "test@example.com"},
                follow_redirects=False,
            )
        assert resp.status_code == 200
        assert "Check your email" in resp.text

    def test_verify_valid_token_sets_cookie(self) -> None:
        import os
        import tempfile

        from briefd.auth import AuthStore, generate_token

        with tempfile.TemporaryDirectory() as td:
            db = os.path.join(td, "auth.db")
            store = AuthStore(db)
            token = generate_token()
            store.save_token(token, email="user@example.com")

            with patch("briefd.web.app.get_auth_store", return_value=store):
                resp = self.client.get(f"/auth/verify?token={token}", follow_redirects=False)

        assert resp.status_code == 303
        assert "briefd_user" in resp.cookies

    def test_verify_invalid_token_returns_400(self) -> None:
        resp = self.client.get("/auth/verify?token=badtoken")
        assert resp.status_code == 400
