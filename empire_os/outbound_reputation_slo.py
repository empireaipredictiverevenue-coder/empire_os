"""Deliverability SLO/error-budget model for sender pools."""
from __future__ import annotations

from typing import Any, Mapping


def evaluate_reputation_slo(context: Mapping[str, Any]) -> dict[str, Any]:
    sent = max(0, int(context.get("sent") or 0))
    bounces = max(0, int(context.get("bounces") or 0))
    complaints = max(0, int(context.get("complaints") or 0))
    spam_placements = max(0, int(context.get("spam_placements") or 0))
    seed_tests = max(0, int(context.get("seed_tests") or 0))

    bounce_budget = max(1, int(sent * 0.02)) if sent else 0
    complaint_budget = max(0, int(sent * 0.0005)) if sent else 0
    spam_budget = max(1, int(seed_tests * 0.10)) if seed_tests else 0

    bounce_remaining = bounce_budget - bounces
    complaint_remaining = complaint_budget - complaints
    spam_remaining = spam_budget - spam_placements

    exhausted = []
    if bounce_remaining < 0:
        exhausted.append("bounce_budget")
    if complaint_remaining < 0:
        exhausted.append("complaint_budget")
    if seed_tests and spam_remaining < 0:
        exhausted.append("placement_budget")

    return {
        "status": "EXHAUSTED" if exhausted else "WITHIN_BUDGET",
        "budgets": {
            "bounce": {"allowed": bounce_budget, "used": bounces, "remaining": bounce_remaining},
            "complaint": {
                "allowed": complaint_budget,
                "used": complaints,
                "remaining": complaint_remaining,
            },
            "spam_placement": {
                "allowed": spam_budget,
                "used": spam_placements,
                "remaining": spam_remaining,
            },
        },
        "exhausted": exhausted,
        "meaning": "error_budget_for_reputation_not_permission_to_generate_errors",
    }
