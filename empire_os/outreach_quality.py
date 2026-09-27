"""Outreach quality reviews for deliverability and evidence-backed messaging.

These functions are analysis-only and cannot configure DNS, providers or send.
"""
from __future__ import annotations

from typing import Any, Mapping


def _text(value: Any) -> str:
    return str(value or "").strip()


def _rate(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        rate = float(value)
    except (TypeError, ValueError):
        return None
    return rate if 0 <= rate <= 1 else None


def review_deliverability(
    evidence: Mapping[str, Any] | None,
    *,
    max_bounce_rate: float = 0.05,
    max_complaint_rate: float = 0.001,
) -> dict[str, Any]:
    """Apply an explicit internal review policy to observed send-health evidence."""
    evidence = dict(evidence or {})
    blockers: list[str] = []
    unknowns: list[str] = []

    for field in ("sending_domain_verified", "spf_verified", "dkim_verified", "dmarc_verified"):
        value = evidence.get(field)
        if value is False:
            blockers.append(f"{field}_failed")
        elif value is not True:
            unknowns.append(f"{field}_unknown")

    bounce = _rate(evidence.get("bounce_rate"))
    complaints = _rate(evidence.get("complaint_rate"))
    if bounce is None:
        unknowns.append("bounce_rate_unknown")
    elif bounce > max_bounce_rate:
        blockers.append("bounce_rate_above_internal_policy")
    if complaints is None:
        unknowns.append("complaint_rate_unknown")
    elif complaints > max_complaint_rate:
        blockers.append("complaint_rate_above_internal_policy")

    provider_ready = evidence.get("provider_ready")
    if provider_ready is False:
        blockers.append("provider_not_ready")
    elif provider_ready is not True:
        unknowns.append("provider_readiness_unknown")

    return {
        "policy": {
            "max_bounce_rate": max_bounce_rate,
            "max_complaint_rate": max_complaint_rate,
            "policy_type": "empire_internal_review_threshold",
        },
        "observed": {
            "sending_domain_verified": evidence.get("sending_domain_verified"),
            "spf_verified": evidence.get("spf_verified"),
            "dkim_verified": evidence.get("dkim_verified"),
            "dmarc_verified": evidence.get("dmarc_verified"),
            "bounce_rate": bounce,
            "complaint_rate": complaints,
            "provider_ready": provider_ready,
        },
        "blockers": blockers,
        "unknowns": unknowns,
        "ready_for_send_review": not blockers and not unknowns,
        "execution_authority": "none",
        "dns_mutation": False,
        "provider_mutation": False,
    }


def build_message_brief(
    *,
    business_name: str,
    contact_name: str | None,
    contact_title: str | None,
    play_type: str,
    offer_key: str | None,
    corridor_key: str | None,
    territory: str | None,
    reason_now: str,
    evidence_refs: list[str],
    predicted_economics: Mapping[str, Any],
) -> dict[str, Any]:
    """Create constraints for proof-led copy without inventing claims."""
    proof_available = bool(evidence_refs)
    prediction_ref = _text(predicted_economics.get("prediction_ref"))
    expected_gp = predicted_economics.get("expected_gross_profit_cents")

    if play_type == "renewal":
        objective = "review realized value and renewal fit"
        cta = "ask for a short renewal/value review"
    elif play_type in {"seat_expansion", "territory_expansion", "capacity_fill"}:
        objective = "review evidence-backed expansion capacity"
        cta = "ask whether the buyer wants the expansion evidence reviewed"
    elif play_type == "reactivation":
        objective = "show what materially changed since the prior conversation"
        cta = "ask whether the changed evidence makes a new review worthwhile"
    elif play_type in {"managed_service_cross_sell", "intelligence_cross_sell"}:
        objective = "connect observed need to an adjacent Empire product"
        cta = "ask permission to share the relevant product/evidence brief"
    else:
        objective = "open a relevant buyer conversation from fresh evidence"
        cta = "ask permission to share the concise evidence-backed opportunity brief"

    personalization = {
        "business_name": business_name,
        "contact_name": contact_name,
        "contact_title": contact_title,
        "territory": territory,
        "corridor_key": corridor_key,
        "reason_now": reason_now,
    }
    personalization = {k: v for k, v in personalization.items() if v}

    return {
        "objective": objective,
        "personalization_inputs": personalization,
        "offer_key": offer_key,
        "opening_rule": "lead with the observed trigger/relevance; do not imply a relationship that is not evidenced",
        "proof_rule": (
            "use only claims supported by evidence_refs"
            if proof_available
            else "no commercial proof claim is permitted until evidence exists"
        ),
        "economics_rule": (
            "prediction may inform prioritisation but must not be presented as actual revenue"
            if prediction_ref or expected_gp is not None
            else "do not invent ROI, savings, revenue or gross-profit claims"
        ),
        "cta": cta,
        "forbidden_claims": [
            "fabricated customer results",
            "invented scarcity or territory demand",
            "guaranteed revenue or conversion",
            "unverified pricing",
            "fake familiarity or prior relationship",
            "claims based on unknown evidence",
            "prediction represented as actual revenue",
        ],
        "evidence_refs": list(evidence_refs),
        "drafting_only": True,
        "send_enabled": False,
        "execution_authority": "none",
    }
