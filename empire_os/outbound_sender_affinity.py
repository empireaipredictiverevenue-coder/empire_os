"""Thread and sender-affinity policy.

Existing conversations stay with the same legitimate sender identity whenever healthy.
"""
from __future__ import annotations

from typing import Any, Mapping


def resolve_sender_affinity(context: Mapping[str, Any]) -> dict[str, Any]:
    prior_sender = str(context.get("prior_sender_id") or "").strip()
    proposed_sender = str(context.get("proposed_sender_id") or "").strip()
    prior_sender_health = str(context.get("prior_sender_health") or "UNKNOWN")
    is_existing_thread = context.get("is_existing_thread") is True

    if not is_existing_thread:
        return {
            "decision": "NEW_THREAD",
            "required_sender_id": None,
            "reason": "no_existing_thread",
        }

    if not prior_sender:
        return {
            "decision": "ESCALATE",
            "required_sender_id": None,
            "reason": "prior_sender_unknown",
        }

    if prior_sender_health == "GREEN":
        if proposed_sender and proposed_sender != prior_sender:
            return {
                "decision": "HOLD",
                "required_sender_id": prior_sender,
                "reason": "sender_affinity_violation",
            }
        return {
            "decision": "READY",
            "required_sender_id": prior_sender,
            "reason": "continue_same_sender",
        }

    return {
        "decision": "ESCALATE",
        "required_sender_id": prior_sender,
        "reason": "prior_sender_unhealthy_requires_governed_migration",
    }
