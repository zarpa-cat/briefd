"""Magic link authentication for Briefd.

Flow:
  1. User submits email → POST /auth/request
  2. Server generates a token, stores it, sends email with link
  3. User clicks link → GET /auth/verify?token=xxx
  4. Server marks token used, sets session cookie
  5. Cookie contains user_id (email-derived) — signed by FastAPI's response

Email sending is handled by send_magic_link(). If RESEND_API_KEY is not set,
it logs the link instead (useful for local dev).
"""

from __future__ import annotations

import logging
import secrets
import sqlite3
from enum import Enum
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

CREATE_TOKENS_TABLE = """
CREATE TABLE IF NOT EXISTS auth_tokens (
    token       TEXT PRIMARY KEY,
    email       TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    used        INTEGER NOT NULL DEFAULT 0
)
"""


class TokenStatus(Enum):
    VALID = "valid"
    INVALID = "invalid"
    ALREADY_USED = "already_used"


def generate_token() -> str:
    """Generate a URL-safe random token."""
    return secrets.token_urlsafe(32)


class AuthStore:
    """SQLite-backed store for magic link tokens."""

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
            conn.execute(CREATE_TOKENS_TABLE)

    def save_token(self, token: str, email: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO auth_tokens (token, email) VALUES (?, ?)",
                (token, email),
            )

    def get_token(self, token: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT token, email, used FROM auth_tokens WHERE token = ?",
                (token,),
            ).fetchone()
        if row is None:
            return None
        return {"token": row["token"], "email": row["email"], "used": bool(row["used"])}

    def mark_used(self, token: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE auth_tokens SET used = 1 WHERE token = ?",
                (token,),
            )


def verify_token(store: AuthStore, token: str) -> tuple[TokenStatus, str]:
    """Verify a magic link token. Returns (status, email).

    On VALID: marks the token as used (one-time use).
    """
    record = store.get_token(token)
    if record is None:
        return TokenStatus.INVALID, ""
    if record["used"]:
        return TokenStatus.ALREADY_USED, ""
    store.mark_used(token)
    return TokenStatus.VALID, record["email"]


def email_to_user_id(email: str) -> str:
    """Derive a stable user_id from an email address."""
    return email.lower().strip()


async def send_magic_link(email: str, token: str, base_url: str) -> None:
    """Send a magic link email via Resend.

    Falls back to logging the link if RESEND_API_KEY is not set
    (useful for local development).
    """
    import os

    verify_url = f"{base_url}/auth/verify?token={token}"
    api_key = os.environ.get("RESEND_API_KEY", "")

    if not api_key:
        logger.info("Magic link (no RESEND_API_KEY): %s", verify_url)
        return

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "from": "Briefd <hello@briefd.ai>",
                "to": [email],
                "subject": "Your Briefd sign-in link",
                "html": (
                    f"<p>Click the link below to sign in to Briefd. "
                    f"It expires after one use.</p>"
                    f'<p><a href="{verify_url}">Sign in to Briefd</a></p>'
                    f"<p style='color:#999;font-size:12px'>{verify_url}</p>"
                ),
            },
        )
        resp.raise_for_status()
