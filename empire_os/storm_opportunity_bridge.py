"""Truth-preserving Storm -> Opportunity Radar adapter.

Converts an already-evaluated StormProductAssessment into canonical opportunity
intelligence without manufacturing buyer intent, demand, economics, revenue or
execution authority.

This module is deterministic, side-effect free and OBSERVE only.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from empire_os.storm_product_integration import (
    AffectedSubject,
    StormEvent,
    StormProductAssessment,
)


def _key(*parts: str) -> str:
    identity = "|".join(str(p).strip().casefold() for p in parts)
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    return f"storm:{digest}"


def decision_opportunity_provenance(snapshot, *, tenant_id, event_id, subject_id, as_of):
    """Replay canonical decisions; retain scope and non-economic semantics."""
    from empire_os.real_world_decision_intelligence import replay_decision_snapshot

    decision = replay_decision_snapshot(snapshot)
    context = decision.context
    if context.tenant_id != tenant_id or context.event_id != event_id:
        raise ValueError("decision opportunity tenant/event mismatch")
    if context.subject_id is not None and context.subject_id != subject_id:
        raise ValueError("decision opportunity subject mismatch")
    now = datetime.fromisoformat(as_of.replace("Z", "+00:00")) if isinstance(as_of, str) else as_of
    generated = datetime.fromisoformat(snapshot["generated_at"].replace("Z", "+00:00"))
    if generated > now:
        raise ValueError("decision opportunity future snapshot")
    freshness = decision.freshness_at(now)
    # Rebuild to avoid aliasing caller-owned mutable snapshot data.
    from empire_os.real_world_decision_intelligence import build_decision_snapshot
    canonical = build_decision_snapshot(decision, generated_at=generated)
    row = canonical["decision"]
    selected = next((c for c in row["candidates"]
                     if c["candidate_id"] == decision.recommended_candidate), None)
    requirements = []
    if freshness != "CURRENT":
        requirements.append({"required": "refresh_decision_evidence", "execution_authority": "none"})
    elif decision.state.value == "GATHER_EVIDENCE":
        requirements = list(selected["information_requests"]) if selected else []
    return {
        "schema_version": canonical["schema_version"],
        "snapshot_hash": canonical["snapshot_hash"],
        "decision_id": decision.decision_id,
        "tenant_id": context.tenant_id,
        "event_id": context.event_id,
        "subject_id": context.subject_id,
        "scope_level": "event" if context.subject_id is None else "subject",
        "as_of": row["context"]["as_of"],
        "generated_at": canonical["generated_at"],
        "state": decision.state.value,
        "selected_candidate": selected,
        "reason_codes": row["reason_codes"],
        "waiting_risk": row["waiting_risk"],
        "freshness": freshness,
        "freshness_as_of": now.isoformat(),
        "truth_class": "DECISION_PROVENANCE",
        "research_requirements": requirements,
        "snapshot": canonical,
        "execution_authority": "none",
        "outreach_authority": "none",
        "calls_authority": "none",
        "traffic_authority": "none",
        "commercial_authority": "none",
        "payment_authority": "none",
        "revenue_recognition_authority": "none",
    }


def storm_assessment_to_opportunity(
    event: StormEvent,
    subject: AffectedSubject,
    assessment: StormProductAssessment,
    *,
    decision_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return one tenant-scoped Radar candidate from verified Storm evidence."""
    tenant_id, event_id, subject_id, buyer_id, product_id = assessment.scope

    if event.tenant_id != tenant_id or subject.tenant_id != tenant_id:
        raise ValueError("storm opportunity tenant mismatch")
    if event.event_id != event_id or subject.event_id != event_id:
        raise ValueError("storm opportunity event mismatch")
    if subject.canonical_id != subject_id:
        raise ValueError("storm opportunity subject mismatch")

    refs = tuple(dict.fromkeys(
        str(ref).strip()
        for ref in assessment.evidence_refs
        if str(ref).strip()
    ))
    if not refs:
        raise ValueError("storm opportunity evidence required")

    score = assessment.score
    match = assessment.match

    # Storm priority is modeled evidence metadata only. It is deliberately NOT
    # mapped onto Opportunity Factory buyer_intent/demand/economics scores.
    storm_model = None
    if score is not None:
        storm_model = {
            "priority_boost": score.priority_boost,
            "multiplier": score.multiplier,
            "model_version": score.model_version,
            "truth_class": score.truth_class.value,
            "evidence_refs": list(score.evidence_refs),
        }

    products: list[dict[str, Any]] = []
    if match is not None:
        products.append({
            "buyer_id": match.buyer_id,
            "product_id": match.product_id,
            "niche": match.niche,
            "territory_id": match.territory_id,
            "evidence_refs": [e.ref for e in match.evidence],
        })

    blockers = list(dict.fromkeys(assessment.blockers))

    result = {
        "opportunity_key": _key(
            tenant_id, event_id, subject_id, buyer_id, product_id
        ),
        "opportunity_class": "storm_commercial_signal",
        "source": "storm_product_integration",
        "title": (
            f"Observed {event.event_type} signal — "
            f"{subject.niche} / {subject.territory_id}"
        ),
        "tenant_id": tenant_id,
        "event_id": event_id,
        "subject_id": subject_id,
        "subject_kind": subject.kind.value,
        "buyer_id": buyer_id,
        "product_id": product_id,
        "niche": subject.niche,
        "territory_id": subject.territory_id,
        "trigger": "observed_storm_commercial_signal",
        "event_type": event.event_type,
        "event_severity": event.severity,
        "event_truth_class": event.truth_class.value,
        "subject_truth_class": subject.truth_class.value,
        "subject_confidence": subject.confidence,
        "territory_overlap": subject.territory_overlap,
        "evaluated_at": assessment.evaluated_at.isoformat(),
        "observed_priority_score": (
            score.priority_boost if score is not None else None
        ),
        "storm_model": storm_model,
        "evidence_strength": (
            "modeled_storm_signal" if score is not None
            else "blocked_storm_signal"
        ),
        "evidence_refs": list(refs),
        "offer_key": None,
        "products": products,
        "storm_blockers": blockers,
        "recommended_next_actions": [
            "complete_canonical_opportunity_evidence",
            "preserve_founder_commercial_authority",
        ],
        "buyer_intent_inferred": False,
        "demand_inferred": False,
        "pricing_inferred": False,
        "market_share_inferred": False,
        "revenue_inferred": False,
        "opportunity_factory_ready": False,
        "factory_blockers": [
            "canonical_buyer_intent_required",
            "demand_evidence_required",
            "economics_evidence_required",
            "distribution_path_evidence_required",
            "fulfilment_readiness_evidence_required",
        ],
        "commercial_ready": False,
        "economics": None,
        "execution_authority": "none",
        "outreach_authority": "none",
        "calls_authority": "none",
        "traffic_authority": "none",
        "commercial_authority": "none",
        "payment_authority": "none",
        "revenue_recognition_authority": "none",
    }
    if decision_snapshot is not None:
        result["decision_provenance"] = decision_opportunity_provenance(
            decision_snapshot, tenant_id=tenant_id, event_id=event_id,
            subject_id=subject_id, as_of=assessment.evaluated_at,
        )
    return result


def build_storm_opportunity_snapshot(
    opportunities: list[dict[str, Any]],
    *,
    generated_at: str,
) -> dict[str, Any]:
    """Build the JSON-safe OBSERVE snapshot consumed by Opportunity Radar."""
    if not isinstance(opportunities, list):
        raise ValueError("storm opportunities must be a list")
    if not isinstance(generated_at, str) or not generated_at.strip():
        raise ValueError("generated_at required")

    rows: list[dict[str, Any]] = []
    identities: set[str] = set()

    for raw in opportunities:
        if not isinstance(raw, dict):
            continue

        row = dict(raw)
        key = str(row.get("opportunity_key") or "").strip()
        tenant = str(row.get("tenant_id") or "").strip()
        refs = row.get("evidence_refs")

        if not key or not tenant:
            continue
        if not isinstance(refs, list) or not refs:
            continue
        if key in identities:
            # Ambiguous identity cannot be promoted downstream.
            continue

        identities.add(key)

        if "decision_provenance" in row:
            row["decision_provenance"] = decision_opportunity_provenance(
                row["decision_provenance"]["snapshot"], tenant_id=tenant,
                event_id=row.get("event_id"), subject_id=row.get("subject_id"),
                as_of=generated_at,
            )

        # Snapshot boundary may never carry execution permission.
        row["execution_authority"] = "none"
        row["outreach_authority"] = "none"
        row["calls_authority"] = "none"
        row["traffic_authority"] = "none"
        row["commercial_authority"] = "none"
        row["payment_authority"] = "none"
        row["revenue_recognition_authority"] = "none"
        row["commercial_ready"] = False
        row["revenue_inferred"] = False

        rows.append(row)

    rows.sort(key=lambda row: str(row["opportunity_key"]))

    return {
        "schema_version": "empire.storm_opportunity_snapshot.v1",
        "mode": "OBSERVE",
        "generated_at": generated_at,
        "available": True,
        "candidate_count": len(rows),
        "candidates": rows,
        "automatic_external_execution_allowed": False,
        "execution_authority": "none",
        "outreach_authority": "none",
        "calls_authority": "none",
        "traffic_authority": "none",
        "commercial_authority": "none",
        "payment_authority": "none",
        "revenue_recognition_authority": "none",
    }
