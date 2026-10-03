"""Revenue-aware reputation budgeting.

Ringleader can spend limited sending capacity on the highest-value *already approved*
opportunities. This never authorizes an otherwise ineligible contact or increases the
sender's safety cap.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping


def allocate_reputation_budget(
    opportunities: Iterable[Mapping[str, Any]],
    *,
    capacity: int,
) -> dict[str, Any]:
    if capacity < 0:
        raise ValueError("capacity_must_be_nonnegative")

    eligible: list[dict[str, Any]] = []
    held: list[dict[str, str]] = []

    for row in opportunities:
        item = dict(row)
        opportunity_id = str(item.get("opportunity_id") or "")

        if item.get("approved") is not True:
            held.append({"opportunity_id": opportunity_id, "reason": "not_approved"})
            continue
        if item.get("recipient_verified") is not True:
            held.append({"opportunity_id": opportunity_id, "reason": "recipient_unverified"})
            continue
        if item.get("suppressed") is not False:
            held.append({"opportunity_id": opportunity_id, "reason": "suppression_not_clear"})
            continue

        value = max(0.0, float(item.get("predicted_value") or 0.0))
        confidence = max(0.0, min(1.0, float(item.get("contact_confidence") or 0.0)))
        deliverability_risk = max(
            0.0, min(1.0, float(item.get("deliverability_risk") or 0.0))
        )
        conversation_probability = max(
            0.0, min(1.0, float(item.get("conversation_probability") or 0.0))
        )

        score = value * confidence * (1.0 - deliverability_risk) * (
            0.50 + 0.50 * conversation_probability
        )
        item["_reputation_value_score"] = score
        eligible.append(item)

    eligible.sort(
        key=lambda item: (
            -float(item["_reputation_value_score"]),
            str(item.get("opportunity_id") or ""),
        )
    )

    selected = eligible[:capacity]
    overflow = eligible[capacity:]

    return {
        "capacity": capacity,
        "selected": [
            {
                "opportunity_id": str(item.get("opportunity_id") or ""),
                "reputation_value_score": round(float(item["_reputation_value_score"]), 4),
            }
            for item in selected
        ],
        "deferred": [
            {
                "opportunity_id": str(item.get("opportunity_id") or ""),
                "reason": "capacity_reserved_for_higher_value_approved_opportunities",
            }
            for item in overflow
        ],
        "held": held,
        "policy": "ordering_only_never_authorizes_or_expands_capacity",
    }
