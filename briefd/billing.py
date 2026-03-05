"""RevenueCat billing integration for Briefd.

Handles customer lifecycle, entitlement checks, and credit balance
for the subscription + credits hybrid monetization model.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

RC_BASE = "https://api.revenuecat.com/v2"
CURRENCY_CODE = "CRED"
ENTITLEMENT_KEY = "premium"


class BillingError(Exception):
    """Raised when an RC API call fails."""

    def __init__(self, status_code: int, error_type: str, message: str = "") -> None:
        self.status_code = status_code
        self.error_type = error_type
        super().__init__(f"RC API error {status_code}: {error_type} — {message}")


@dataclass
class CustomerStatus:
    """Billing state for a single customer."""

    customer_id: str
    has_premium: bool
    credit_balance: int

    @property
    def can_afford_briefing(self) -> bool:
        return self.has_premium or self.credit_balance > 0


class BillingClient:
    """Client for RevenueCat v2 API, scoped to billing operations."""

    def __init__(self, api_key: str, project_id: str) -> None:
        self._key = api_key
        self._project_id = project_id

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        }

    async def _get(self, path: str) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{RC_BASE}{path}", headers=self._headers())
        if not resp.is_success:
            body = resp.json()
            raise BillingError(
                resp.status_code, body.get("type", "unknown"), body.get("message", "")
            )
        return resp.json()  # type: ignore[no-any-return]

    async def _post(self, path: str, body: dict) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{RC_BASE}{path}", headers=self._headers(), json=body)
        if not resp.is_success:
            data = resp.json()
            raise BillingError(
                resp.status_code, data.get("type", "unknown"), data.get("message", "")
            )
        return resp.json()  # type: ignore[no-any-return]

    async def create_customer(self, user_id: str) -> str:
        """Create a customer in RC. Idempotent — 409 means already exists."""
        try:
            result = await self._post(
                f"/projects/{self._project_id}/customers",
                {"id": user_id},
            )
            return result["id"]  # type: ignore[no-any-return]
        except BillingError as e:
            if e.status_code == 409:
                # Already exists — fine, return the provided ID
                return user_id
            raise

    async def get_customer_status(self, user_id: str) -> CustomerStatus:
        """Fetch entitlement + credit status for a customer."""
        data = await self._get(f"/projects/{self._project_id}/customers/{user_id}")
        entitlements: dict = data.get("active_entitlements", {})
        has_premium = ENTITLEMENT_KEY in entitlements
        balance = await self.get_credit_balance(user_id)
        return CustomerStatus(
            customer_id=user_id,
            has_premium=has_premium,
            credit_balance=balance,
        )

    async def get_credit_balance(self, user_id: str) -> int:
        """Return the current CRED balance for a customer. Returns 0 if not found."""
        try:
            data = await self._get(
                f"/projects/{self._project_id}/customers/{user_id}"
                f"/virtual_currencies/{CURRENCY_CODE}/balance"
            )
            return int(data.get("balance", 0))
        except BillingError as e:
            if e.status_code == 404:
                return 0
            raise

    def can_generate(self, status: CustomerStatus) -> bool:
        """Return True if the customer is allowed to generate a briefing."""
        return status.has_premium or status.credit_balance > 0
