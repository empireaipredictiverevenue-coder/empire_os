"""Recipient-domain risk policy for autonomous B2B outbound."""
from __future__ import annotations

from typing import Any, Mapping


_CONSUMER_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "ymail.com",
    "aol.com",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "msn.com",
    "icloud.com",
    "me.com",
    "mac.com",
}


def evaluate_recipient_domain_policy(
    context: Mapping[str, Any],
) -> dict[str, Any]:
    domain = str(context.get("recipient_domain") or "").strip().lower()
    traffic_class = str(context.get("traffic_class") or "").strip().lower()
    consented = context.get("consented") is True
    existing_relationship = context.get("existing_relationship") is True
    person_company_bound = context.get("person_company_bound") is True

    consumer = domain in _CONSUMER_DOMAINS
    if (
        consumer
        and traffic_class in {"prospecting", "cold_outbound"}
        and not consented
        and not existing_relationship
    ):
        return {
            "decision": "HOLD",
            "reason": "unconsented_consumer_mailbox_prospecting",
            "consumer_mailbox": True,
            "recipient_domain": domain,
        }

    if not person_company_bound and traffic_class in {"prospecting", "cold_outbound"}:
        return {
            "decision": "ESCALATE",
            "reason": "recipient_not_bound_to_business_identity",
            "consumer_mailbox": consumer,
            "recipient_domain": domain,
        }

    return {
        "decision": "READY",
        "reason": "recipient_domain_policy_clear",
        "consumer_mailbox": consumer,
        "recipient_domain": domain,
    }
