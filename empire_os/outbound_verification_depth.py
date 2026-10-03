"""Adaptive recipient-verification depth planner.

Predicted commercial value may justify *more verification*, never weaker verification or
more sending authority.
"""
from __future__ import annotations

from typing import Any, Mapping


def verification_plan(context: Mapping[str, Any]) -> dict[str, Any]:
    value = max(0.0, float(context.get("predicted_value") or 0.0))
    confidence = max(0.0, min(1.0, float(context.get("contact_confidence") or 0.0)))
    historical_domain_bounce = max(
        0.0, min(1.0, float(context.get("historical_domain_bounce_rate") or 0.0))
    )
    catch_all = context.get("catch_all") is True

    risk = (1.0 - confidence) * 0.5 + min(1.0, historical_domain_bounce / 0.05) * 0.4
    if catch_all:
        risk += 0.1
    risk = min(1.0, risk)

    checks = [
        "syntax",
        "mx_exists",
        "suppression_history",
        "historical_delivery_evidence",
        "person_company_binding",
    ]

    if risk >= 0.35 or value >= 5000:
        checks.extend([
            "domain_reputation_history",
            "role_account_detection",
            "source_provenance_review",
        ])

    if risk >= 0.60 or value >= 15000:
        checks.extend([
            "manual_or_agentic_identity_crosscheck",
            "decision_maker_evidence_refresh",
            "recent_contact_evidence_required",
        ])

    if catch_all:
        outcome = "ESCALATE"
    elif risk >= 0.70:
        outcome = "HOLD"
    else:
        outcome = "VERIFY"

    return {
        "outcome": outcome,
        "risk": round(risk, 4),
        "checks": list(dict.fromkeys(checks)),
        "principle": "value_increases_verification_depth_not_send_permission",
    }
