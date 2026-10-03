"""Reputation Economic Memory for Empire outbound.

Records the commercial yield and reputation cost of a bounded sending cohort. This module
does not authorize sending and does not treat opens/clicks as commercial success.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class ReputationEconomicsPolicy:
    hard_bounce_cost: float = 6.0
    complaint_cost: float = 25.0
    opt_out_cost: float = 4.0
    deferral_cost: float = 0.5
    spam_placement_cost: float = 2.0
    missing_placement_cost: float = 3.0


def score_cohort(
    context: Mapping[str, Any],
    *,
    policy: ReputationEconomicsPolicy | None = None,
) -> dict[str, Any]:
    policy = policy or ReputationEconomicsPolicy()

    sent = max(0, int(context.get("sent") or 0))
    positive_replies = max(0, int(context.get("positive_replies") or 0))
    meetings = max(0, int(context.get("meetings") or 0))
    proposals = max(0, int(context.get("proposals") or 0))
    hard_bounces = max(0, int(context.get("hard_bounces") or 0))
    complaints = max(0, int(context.get("complaints") or 0))
    opt_outs = max(0, int(context.get("opt_outs") or 0))
    deferrals = max(0, int(context.get("deferrals") or 0))
    spam_placements = max(0, int(context.get("spam_placements") or 0))
    missing_placements = max(0, int(context.get("missing_placements") or 0))
    actual_revenue = max(0.0, float(context.get("actual_revenue") or 0.0))
    predicted_pipeline = max(0.0, float(context.get("predicted_pipeline") or 0.0))

    reputation_cost = (
        hard_bounces * policy.hard_bounce_cost
        + complaints * policy.complaint_cost
        + opt_outs * policy.opt_out_cost
        + deferrals * policy.deferral_cost
        + spam_placements * policy.spam_placement_cost
        + missing_placements * policy.missing_placement_cost
    )

    commercial_signal = (
        positive_replies * 1.0
        + meetings * 3.0
        + proposals * 5.0
        + (actual_revenue / 1000.0)
        + (predicted_pipeline / 5000.0)
    )

    efficiency = commercial_signal / max(1.0, reputation_cost)
    if reputation_cost == 0 and commercial_signal > 0:
        band = "EXCELLENT"
    elif efficiency >= 3.0:
        band = "STRONG"
    elif efficiency >= 1.0:
        band = "POSITIVE"
    elif commercial_signal > 0:
        band = "WEAK"
    else:
        band = "NEGATIVE"

    return {
        "band": band,
        "sent": sent,
        "commercial_signal": round(commercial_signal, 4),
        "reputation_cost": round(reputation_cost, 4),
        "commercial_value_per_reputation_cost": round(efficiency, 4),
        "actual_revenue": actual_revenue,
        "predicted_pipeline": predicted_pipeline,
        "uses_opens_as_success_signal": False,
    }


def summarize_memory(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [dict(row) for row in records]
    if not rows:
        return {
            "cohorts": 0,
            "commercial_signal": 0.0,
            "reputation_cost": 0.0,
            "efficiency": 0.0,
        }

    commercial = sum(float(row.get("commercial_signal") or 0) for row in rows)
    cost = sum(float(row.get("reputation_cost") or 0) for row in rows)
    return {
        "cohorts": len(rows),
        "commercial_signal": round(commercial, 4),
        "reputation_cost": round(cost, 4),
        "efficiency": round(commercial / max(1.0, cost), 4),
    }
