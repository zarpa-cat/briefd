"""RevenueCat webhook handler for Briefd.

RC sends events for key subscription lifecycle moments. Handling these
event-driven allows the agent to act without polling: grant credits on
renewal, trigger churn intervention on cancellation, flag billing issues.

Reference: https://www.revenuecat.com/docs/integrations/webhooks
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class WebhookEventType(Enum):
    INITIAL_PURCHASE = "INITIAL_PURCHASE"
    RENEWAL = "RENEWAL"
    CANCELLATION = "CANCELLATION"
    BILLING_ISSUE = "BILLING_ISSUE"
    EXPIRATION = "EXPIRATION"
    UNCANCELLATION = "UNCANCELLATION"
    PRODUCT_CHANGE = "PRODUCT_CHANGE"
    UNKNOWN = "UNKNOWN"


@dataclass
class WebhookEvent:
    event_type: WebhookEventType
    user_id: str
    product_id: str


def parse_webhook(payload: dict) -> WebhookEvent:
    """Parse a raw RC webhook payload into a typed WebhookEvent."""
    event = payload.get("event", {})
    raw_type = event.get("type", "")
    try:
        event_type = WebhookEventType(raw_type)
    except ValueError:
        event_type = WebhookEventType.UNKNOWN

    return WebhookEvent(
        event_type=event_type,
        user_id=event.get("app_user_id", ""),
        product_id=event.get("product_id", ""),
    )


async def handle_webhook(event: WebhookEvent) -> list[str]:
    """Handle a parsed webhook event. Returns list of action descriptions taken.

    This is the agent's event-driven intervention layer. Each event type
    maps to a set of autonomous actions the agent takes on behalf of the user.
    """
    match event.event_type:
        case WebhookEventType.INITIAL_PURCHASE:
            return await _on_initial_purchase(event)
        case WebhookEventType.RENEWAL:
            return await _on_renewal(event)
        case WebhookEventType.CANCELLATION:
            return await _on_cancellation(event)
        case WebhookEventType.BILLING_ISSUE:
            return await _on_billing_issue(event)
        case WebhookEventType.EXPIRATION:
            return await _on_expiration(event)
        case WebhookEventType.UNCANCELLATION:
            return await _on_uncancellation(event)
        case _:
            logger.info("Ignoring unknown event type: %s", event.event_type)
            return []


async def _on_initial_purchase(event: WebhookEvent) -> list[str]:
    """New subscriber — onboard them."""
    logger.info("Initial purchase: user=%s product=%s", event.user_id, event.product_id)
    # TODO Phase 4: send welcome briefing, set up delivery schedule
    return [f"onboard:{event.user_id}", f"schedule_delivery:{event.user_id}"]


async def _on_renewal(event: WebhookEvent) -> list[str]:
    """Subscription renewed — RC handles credit grant automatically via product grants."""
    logger.info("Renewal: user=%s", event.user_id)
    # Credits are granted by RC automatically via virtual currency product grants.
    # We just log + could send a notification.
    return [f"renewal_acknowledged:{event.user_id}"]


async def _on_cancellation(event: WebhookEvent) -> list[str]:
    """Subscriber cancelled — start churn intervention flow."""
    logger.info("Cancellation: user=%s", event.user_id)
    # TODO Phase 4: queue win-back email draft for agent review
    return [f"churn_intervention:{event.user_id}", f"cancel_delivery_schedule:{event.user_id}"]


async def _on_billing_issue(event: WebhookEvent) -> list[str]:
    """Billing failed — grace period window open."""
    logger.info("Billing issue: user=%s", event.user_id)
    # Grace period = intervention window. User still has access.
    # TODO Phase 4: send payment reminder, offer discount code
    return [f"billing_grace_period:{event.user_id}", f"queue_payment_reminder:{event.user_id}"]


async def _on_expiration(event: WebhookEvent) -> list[str]:
    """Subscription expired — downgrade experience."""
    logger.info("Expiration: user=%s", event.user_id)
    # TODO Phase 4: switch user to free tier, send re-engagement email
    return [f"downgrade_to_free:{event.user_id}"]


async def _on_uncancellation(event: WebhookEvent) -> list[str]:
    """User reversed their cancellation."""
    logger.info("Uncancellation: user=%s", event.user_id)
    return [f"resume_delivery:{event.user_id}"]
