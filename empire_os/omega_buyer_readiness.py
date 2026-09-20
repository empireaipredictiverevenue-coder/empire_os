"""Read-only Omega 2 -> verified buyer-capacity readiness."""
from __future__ import annotations

import urllib.parse
from typing import Any, Mapping

from empire_os.buyer_allocation import (
    buyer_activation_decision,
    fetch_active_identity_link,
    fetch_buyer_rows,
    fetch_latest_qualification,
    plan_allocation,
)
from empire_os.lead_scoring_v2 import MIN_DECISION_CONFIDENCE
from empire_os.omega_worker import SCORE_TYPE
from empire_os.qualification_worker_v2 import request_json


class OmegaBuyerReadinessError(RuntimeError):
    pass


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def omega_readiness_decision(
    omega_score: Mapping[str, Any] | None,
    qualification: Mapping[str, Any] | None,
    identity_link: Mapping[str, Any] | None,
) -> tuple[bool, str]:
    if not isinstance(omega_score, Mapping):
        return False, "omega_score_missing"
    if _text(omega_score.get("score_type")) != SCORE_TYPE:
        return False, "omega_score_type_invalid"

    confidence = _number(omega_score.get("confidence"))
    if confidence is None:
        return False, "omega_confidence_missing"
    if confidence < MIN_DECISION_CONFIDENCE:
        return False, "omega_confidence_below_floor"

    if not isinstance(qualification, Mapping):
        return False, "qualification_missing"
    if _text(qualification.get("scoring_version")) != "v2":
        return False, "qualification_v2_required"
    if _text(qualification.get("status")) != "scored":
        return False, "qualification_not_scored"

    features = omega_score.get("features")
    if not isinstance(features, Mapping):
        return False, "omega_features_missing"

    prospect_id = _text(qualification.get("prospect_id"))
    entity_id = _text(qualification.get("entity_id"))
    qualification_id = _text(qualification.get("id"))
    if not prospect_id or not entity_id or not qualification_id:
        return False, "qualification_identity_missing"

    if _text(features.get("prospect_id")) != prospect_id:
        return False, "omega_prospect_mismatch"
    if _text(features.get("qualification_id")) != qualification_id:
        return False, "omega_qualification_mismatch"
    if _text(omega_score.get("entity_id")) != entity_id:
        return False, "omega_entity_mismatch"

    if not isinstance(identity_link, Mapping):
        return False, "identity_link_missing"
    if identity_link.get("active") is not True:
        return False, "identity_link_inactive"
    if _text(identity_link.get("prospect_id")) != prospect_id:
        return False, "identity_prospect_mismatch"
    if _text(identity_link.get("entity_id")) != entity_id:
        return False, "identity_entity_mismatch"

    return True, "omega_identity_ready"


def assess_omega_buyer_readiness(
    *,
    prospect: dict[str, Any],
    qualification: dict[str, Any] | None,
    identity_link: dict[str, Any] | None,
    omega_score: dict[str, Any] | None,
    buyers: list[dict[str, Any]],
) -> dict[str, Any]:
    prospect_id = _text(prospect.get("id"))
    allowed, reason = omega_readiness_decision(
        omega_score,
        qualification,
        identity_link,
    )
    if not allowed:
        return {
            "prospect_id": prospect_id,
            "decision": "not_ready",
            "reason": reason,
            "omega_ready": False,
            "buyer_capacity_ready": False,
            "candidate_count": 0,
            "candidates": [],
            "allocation_executed": False,
            "recognized_revenue_written": False,
        }

    plan = plan_allocation(
        prospect,
        qualification,
        identity_link,
        buyers,
    )
    candidates = list(plan.get("candidates") or [])
    buyer_ready = plan.get("decision") == "ready" and bool(candidates)
    return {
        "prospect_id": prospect_id,
        "entity_id": _text(omega_score.get("entity_id")),
        "omega_score": omega_score.get("score"),
        "omega_confidence": omega_score.get("confidence"),
        "expected_revenue": (omega_score.get("features") or {}).get(
            "expected_revenue"
        ),
        "expected_gross_profit": (omega_score.get("features") or {}).get(
            "expected_gross_profit"
        ),
        "decision": (
            "buyer_capacity_ready"
            if buyer_ready
            else "no_verified_buyer_capacity"
        ),
        "reason": (
            "verified_buyer_capacity_available"
            if buyer_ready
            else plan.get("reason") or "no_eligible_buyer_capacity"
        ),
        "omega_ready": True,
        "buyer_capacity_ready": buyer_ready,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "allocation_executed": False,
        "recognized_revenue_written": False,
    }


def _reader(path: str, params: dict[str, str]) -> Any:
    query = urllib.parse.urlencode(params)
    return request_json("GET", f"{path}?{query}")


def fetch_recent_omega_scores(limit: int = 10) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 25))
    params = urllib.parse.urlencode(
        {
            "select": (
                "id,entity_id,score_type,score,confidence,model_key,"
                "features,explanation,scored_at"
            ),
            "entity_type": "eq.company",
            "score_type": f"eq.{SCORE_TYPE}",
            "order": "scored_at.desc",
            "limit": limit,
        }
    )
    rows = request_json(
        "GET",
        f"/rest/v1/intelligence_scores?{params}",
    ) or []
    return [row for row in rows if isinstance(row, dict)]


def fetch_prospect(prospect_id: str) -> dict[str, Any] | None:
    params = urllib.parse.urlencode(
        {
            "select": "id,business_name,niche,metro,status",
            "id": f"eq.{prospect_id}",
            "limit": 1,
        }
    )
    rows = request_json("GET", f"/rest/v1/prospects?{params}") or []
    return rows[0] if rows else None


def run_omega_buyer_readiness_cycle(limit: int = 10) -> dict[str, Any]:
    scores = fetch_recent_omega_scores(limit)
    buyers = fetch_buyer_rows(_reader)
    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for score in scores:
        features = score.get("features")
        prospect_id = (
            _text(features.get("prospect_id"))
            if isinstance(features, Mapping)
            else ""
        )
        if not prospect_id:
            errors.append(
                {
                    "prospect_id": "",
                    "error": "OmegaBuyerReadinessError:omega prospect missing",
                }
            )
            continue
        try:
            prospect = fetch_prospect(prospect_id)
            if not prospect:
                raise OmegaBuyerReadinessError("prospect missing")
            qualification = fetch_latest_qualification(
                _reader,
                prospect_id,
            )
            identity_link = fetch_active_identity_link(
                _reader,
                prospect_id,
            )
            results.append(
                assess_omega_buyer_readiness(
                    prospect=prospect,
                    qualification=qualification,
                    identity_link=identity_link,
                    omega_score=score,
                    buyers=buyers,
                )
            )
        except Exception as exc:
            errors.append(
                {
                    "prospect_id": prospect_id,
                    "error": f"{type(exc).__name__}:{str(exc)[:300]}",
                }
            )

    commercially_activated = [
        row for row in buyers
        if buyer_activation_decision(row)[0]
    ]
    terms_verified = [
        row for row in buyers
        if row.get("commercial_terms_verified_at")
        and str(row.get("commercial_terms_source") or "").strip()
        and str(row.get("commercial_terms_reference") or "").strip()
    ]
    capacity_ready = [
        row for row in commercially_activated
        if int(row.get("daily_cap") or 0) > int(row.get("calls_today") or 0)
    ]

    return {
        "schema_version": "omega_buyer_readiness.v2",
        "ok": not errors,
        "scores_seen": len(scores),
        "buyers_seen": len(buyers),
        "buyers_with_verified_terms": len(terms_verified),
        "commercially_activated_buyers": len(commercially_activated),
        "activated_buyers_with_capacity": len(capacity_ready),
        "ready_count": sum(
            1 for item in results
            if item.get("buyer_capacity_ready") is True
        ),
        "blocked_count": sum(
            1 for item in results
            if item.get("buyer_capacity_ready") is not True
        ),
        "results": results,
        "errors": errors,
        "read_only": True,
        "allocation_actions": False,
        "outbound_actions": False,
        "payment_actions": False,
        "recognized_revenue_written": False,
    }
