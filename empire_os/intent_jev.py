"""JEV adjudication layer for Intent Brain decisions.

JEV independently checks whether an Intent Brain conclusion is sufficiently
supported to progress. It may downgrade or block a recommendation.

It can never grant outbound, payment, canonical-ingest or revenue authority.
"""
from __future__ import annotations

from typing import Any, Mapping


SCHEMA_VERSION = "empire.intent_jev.v1"


def adjudicate_intent(
    brain: Mapping[str, Any],
) -> dict[str, Any]:
    confidence = (
        dict(brain.get("confidence") or {})
        if isinstance(brain.get("confidence"), Mapping)
        else {}
    )
    evidence = (
        dict(brain.get("evidence") or {})
        if isinstance(brain.get("evidence"), Mapping)
        else {}
    )

    actor_type = str(brain.get("actor_type") or "unknown")
    brain_decision = str(brain.get("decision") or "WATCH")
    commercial_intent = brain.get("commercial_intent") is True
    first_party_verified = brain.get("first_party_verified") is True
    contradictions = list(brain.get("contradictions") or ())
    negative = list(brain.get("negative_intent_classes") or ())

    intent_conf = float(confidence.get("intent") or 0.0)
    actor_conf = float(confidence.get("actor") or 0.0)
    evidence_conf = float(confidence.get("evidence") or 0.0)
    identity_conf = float(confidence.get("identity") or 0.0)

    blockers: list[str] = []
    supports: list[str] = []

    if commercial_intent:
        supports.append("commercial_intent_supported")
    else:
        blockers.append("commercial_intent_not_supported")

    if actor_type in {"owner_operator", "decision_maker"}:
        supports.append("buyer_authority_actor_supported")
    elif actor_type in {"job_seeker", "vendor"}:
        blockers.append("actor_is_not_buyer")
    else:
        blockers.append("actor_authority_unknown")

    if first_party_verified:
        supports.append("first_party_identity_verified")
    elif int(evidence.get("first_party_candidate_count") or 0) > 0:
        blockers.append("first_party_identity_candidate_unverified")
    else:
        blockers.append("first_party_identity_missing")

    if negative:
        blockers.append("negative_intent_class_present")

    if contradictions:
        blockers.append("contradictory_evidence_present")

    evidence_consistency = (
        intent_conf * 0.35
        + actor_conf * 0.20
        + evidence_conf * 0.20
        + identity_conf * 0.25
    )
    evidence_consistency -= min(0.35, len(contradictions) * 0.12)
    evidence_consistency = max(0.0, min(1.0, evidence_consistency))

    if negative or actor_type in {"job_seeker", "vendor"}:
        recommendation = "REJECT"
        reason = "non_buyer_or_negative_intent"
    elif not commercial_intent:
        recommendation = "WATCH"
        reason = "commercial_intent_not_proven"
    elif len(contradictions) >= 2:
        recommendation = "NEEDS_REVIEW"
        reason = "material_evidence_conflict"
    elif not first_party_verified:
        recommendation = "RESOLVE_IDENTITY"
        reason = "identity_verification_required"
    elif actor_type == "unknown":
        recommendation = "NEEDS_REVIEW"
        reason = "buyer_authority_not_verified"
    elif intent_conf < 0.62 or evidence_consistency < 0.60:
        recommendation = "NEEDS_REVIEW"
        reason = "confidence_below_seed_threshold"
    else:
        recommendation = "BUYER_SCOUT_SEED"
        reason = "evidence_supports_bounded_seed"

    rank = {
        "REJECT": 0,
        "WATCH": 1,
        "RESOLVE_IDENTITY": 2,
        "NEEDS_REVIEW": 3,
        "BUYER_SCOUT_SEED": 4,
    }

    # JEV cannot upgrade above the deterministic brain's authority level.
    if rank.get(recommendation, 0) > rank.get(brain_decision, 0):
        recommendation = brain_decision
        reason = "jev_cannot_upgrade_deterministic_brain"

    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "OBSERVE",
        "brain_schema_version": brain.get("schema_version"),
        "brain_decision": brain_decision,
        "actor_claim_supported": actor_type in {
            "owner_operator",
            "decision_maker",
        },
        "buyer_intent_supported": commercial_intent,
        "niche_supported": str(brain.get("niche") or "unknown") != "unknown",
        "identity_evidence_available": (
            first_party_verified
            or int(evidence.get("first_party_candidate_count") or 0) > 0
        ),
        "first_party_identity_verified": first_party_verified,
        "contradiction_count": len(contradictions),
        "evidence_consistency": round(evidence_consistency, 4),
        "supports": supports,
        "blockers": list(dict.fromkeys(blockers)),
        "recommendation": recommendation,
        "reason": reason,
        "outreach_authorized": False,
        "database_write_performed": False,
        "payment_mutation": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }
