"""Tests for RevenueCat billing integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from briefd.billing import BillingClient, BillingError, CustomerStatus


class TestBillingClient:
    """Tests for the RC billing client."""

    def _client(self) -> BillingClient:
        return BillingClient(api_key="sk_test", project_id="proj_test")

    async def test_get_customer_status_active(self) -> None:
        client = self._client()
        mock_response = {
            "id": "user_123",
            "active_entitlements": {
                "premium": {
                    "lookup_key": "premium",
                    "expires_date": None,
                }
            },
        }
        with patch.object(client, "_get", new_callable=AsyncMock, return_value=mock_response):
            status = await client.get_customer_status("user_123")

        assert status.has_premium is True
        assert status.customer_id == "user_123"

    async def test_get_customer_status_no_entitlement(self) -> None:
        client = self._client()
        mock_response = {
            "id": "user_456",
            "active_entitlements": {},
        }
        with patch.object(client, "_get", new_callable=AsyncMock, return_value=mock_response):
            status = await client.get_customer_status("user_456")

        assert status.has_premium is False

    async def test_create_customer_returns_id(self) -> None:
        client = self._client()
        mock_response = {"id": "user_789", "object": "customer"}
        with patch.object(client, "_post", new_callable=AsyncMock, return_value=mock_response):
            customer_id = await client.create_customer("user_789")

        assert customer_id == "user_789"

    async def test_create_customer_idempotent_on_conflict(self) -> None:
        """409 conflict means customer already exists — should return the ID."""
        client = self._client()
        with patch.object(
            client,
            "_post",
            new_callable=AsyncMock,
            side_effect=BillingError(409, "resource_already_exists"),
        ):
            # Should not raise, just return the provided ID
            customer_id = await client.create_customer("existing_user")

        assert customer_id == "existing_user"

    async def test_get_credit_balance_returns_integer(self) -> None:
        client = self._client()
        mock_response = {"balance": 85, "currency_code": "CRED"}
        with patch.object(client, "_get", new_callable=AsyncMock, return_value=mock_response):
            balance = await client.get_credit_balance("user_123")

        assert balance == 85

    async def test_get_credit_balance_zero_when_not_found(self) -> None:
        client = self._client()
        with patch.object(
            client, "_get", new_callable=AsyncMock, side_effect=BillingError(404, "not_found")
        ):
            balance = await client.get_credit_balance("user_123")

        assert balance == 0

    async def test_can_generate_briefing_requires_premium_or_credits(self) -> None:
        client = self._client()

        # Premium user: yes
        active = CustomerStatus(customer_id="u1", has_premium=True, credit_balance=0)
        assert client.can_generate(active) is True

        # Credits only: yes if balance > 0
        credits_only = CustomerStatus(customer_id="u2", has_premium=False, credit_balance=5)
        assert client.can_generate(credits_only) is True

        # Neither: no
        neither = CustomerStatus(customer_id="u3", has_premium=False, credit_balance=0)
        assert client.can_generate(neither) is False
