"""Tests for the RC webhook handler."""

from __future__ import annotations

from briefd.webhook import WebhookEvent, WebhookEventType, handle_webhook, parse_webhook


class TestParseWebhook:
    def _payload(self, event_type: str, user_id: str = "user_123") -> dict:
        return {
            "event": {
                "type": event_type,
                "app_user_id": user_id,
                "product_id": "premium_monthly",
            }
        }

    def test_parses_initial_purchase(self) -> None:
        event = parse_webhook(self._payload("INITIAL_PURCHASE"))
        assert event.event_type == WebhookEventType.INITIAL_PURCHASE
        assert event.user_id == "user_123"

    def test_parses_renewal(self) -> None:
        event = parse_webhook(self._payload("RENEWAL"))
        assert event.event_type == WebhookEventType.RENEWAL

    def test_parses_cancellation(self) -> None:
        event = parse_webhook(self._payload("CANCELLATION"))
        assert event.event_type == WebhookEventType.CANCELLATION

    def test_parses_billing_issue(self) -> None:
        event = parse_webhook(self._payload("BILLING_ISSUE"))
        assert event.event_type == WebhookEventType.BILLING_ISSUE

    def test_parses_expiration(self) -> None:
        event = parse_webhook(self._payload("EXPIRATION"))
        assert event.event_type == WebhookEventType.EXPIRATION

    def test_unknown_event_type_is_ignored(self) -> None:
        event = parse_webhook(self._payload("SOME_FUTURE_EVENT"))
        assert event.event_type == WebhookEventType.UNKNOWN


class TestHandleWebhook:
    async def test_initial_purchase_logs_action(self) -> None:
        event = WebhookEvent(
            event_type=WebhookEventType.INITIAL_PURCHASE,
            user_id="u1",
            product_id="premium_monthly",
        )
        actions = await handle_webhook(event)
        assert any("onboard" in a or "purchase" in a.lower() for a in actions)

    async def test_cancellation_logs_action(self) -> None:
        event = WebhookEvent(
            event_type=WebhookEventType.CANCELLATION,
            user_id="u1",
            product_id="premium_monthly",
        )
        actions = await handle_webhook(event)
        assert any("churn" in a.lower() or "cancel" in a.lower() for a in actions)

    async def test_billing_issue_logs_action(self) -> None:
        event = WebhookEvent(
            event_type=WebhookEventType.BILLING_ISSUE,
            user_id="u1",
            product_id="premium_monthly",
        )
        actions = await handle_webhook(event)
        assert any("grace" in a.lower() or "billing" in a.lower() for a in actions)

    async def test_unknown_event_returns_no_actions(self) -> None:
        event = WebhookEvent(
            event_type=WebhookEventType.UNKNOWN,
            user_id="u1",
            product_id="",
        )
        actions = await handle_webhook(event)
        assert actions == []
