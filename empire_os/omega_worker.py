"""Bounded canonical Omega 2 projection for evidence-qualified prospects."""
from __future__ import annotations

import urllib.parse
from datetime import datetime, timezone
from typing import Any, Mapping

from empire_os.intelligence.omega import MODEL_VERSION, analyze
from empire_os.lead_scoring_v2 import MIN_DECISION_CONFIDENCE
from empire_os.qualification_worker_v2 import request_json

SCORE_TYPE = "omega_opportunity"


class OmegaWorkerError(RuntimeError):
    """Canonical evidence cannot support an Omega projection."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _confidence(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise OmegaWorkerError("qualification evidence confidence missing") from exc
    if not 0.0 <= number <= 1.0:
        raise OmegaWorkerError("qualification evidence confidence invalid")
    return number
def build_omega_score_row(
    qualification: Mapping[str, Any],
    identity_link: Mapping[str, Any],
) -> dict[str, Any]:
    if _text(qualification.get("scoring_version")) != "v2":
        raise OmegaWorkerError("v2 qualification required")
    if _text(qualification.get("status")) != "scored":
        raise OmegaWorkerError("scored qualification required")

    evidence_confidence = _confidence(
        qualification.get("evidence_confidence")
    )
    if evidence_confidence < MIN_DECISION_CONFIDENCE:
        raise OmegaWorkerError("qualification evidence below decision floor")

    prospect_id = _text(qualification.get("prospect_id"))
    qualification_id = _text(qualification.get("id"))
    entity_id = _text(qualification.get("entity_id"))
    if not prospect_id or not qualification_id or not entity_id:
        raise OmegaWorkerError("qualification identity fields missing")

    if identity_link.get("active") is not True:
        raise OmegaWorkerError("identity link inactive")
    if _text(identity_link.get("prospect_id")) != prospect_id:
        raise OmegaWorkerError("identity link prospect mismatch")
    if _text(identity_link.get("entity_id")) != entity_id:
        raise OmegaWorkerError("identity link entity mismatch")

    snapshot = qualification.get("input_snapshot")
    if not isinstance(snapshot, Mapping):
        raise OmegaWorkerError("qualification input snapshot missing")
    lead = dict(snapshot)
    prediction = analyze(lead)
    scored_at = _text(qualification.get("scored_at"))
    if not scored_at:
        raise OmegaWorkerError("qualification scored_at missing")

    return {
        "entity_type": "company",
        "entity_id": entity_id,
        "score_type": SCORE_TYPE,
        "score": prediction.opportunity_score,
        "confidence": evidence_confidence,
        "model_key": MODEL_VERSION,
        "features": {
            "prospect_id": prospect_id,
            "qualification_id": qualification_id,
            "qualification_score": qualification.get("score"),
            "qualification_tier": qualification.get("tier"),
            "qualification_evidence_confidence": evidence_confidence,
            "model_feature_confidence": prediction.confidence,
            "quality_probability": prediction.quality_probability,
            "buyer_fit_probability": prediction.buyer_fit_probability,
            "engagement_probability": prediction.engagement_probability,
            "conversion_probability": prediction.conversion_probability,
            "payment_probability": prediction.payment_probability,
            "expected_revenue": prediction.expected_revenue,
            "expected_gross_profit": prediction.expected_gross_profit,
            "legacy_omega_score": prediction.legacy_omega_score,
            "legacy_omega_tier": prediction.legacy_omega_tier,
        },
        "explanation": {
            "next_best_action": prediction.next_best_action,
            "reasons": list(prediction.reasons),
            "score_semantics": (
                "deterministic opportunity heuristic; not revenue"
            ),
            "probability_semantics": (
                "deterministic baseline; not outcome-calibrated probability"
            ),
            "confidence_basis": (
                "qualification v2 evidence confidence; evidence sufficiency "
                "rather than outcome-calibrated predictive confidence"
            ),
            "commercial_value_known": prediction.expected_revenue is not None,
            "gross_profit_known": prediction.expected_gross_profit is not None,
        },
        "scored_at": scored_at,
    }
def fetch_omega_candidates(limit: int = 10) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 25))
    params = urllib.parse.urlencode(
        {
            "select": (
                "id,prospect_id,entity_id,score,tier,status,scoring_engine,"
                "scoring_version,evidence_confidence,input_snapshot,scored_at"
            ),
            "scoring_engine": "eq.empire_os.lead_scoring",
            "scoring_version": "eq.v2",
            "status": "eq.scored",
            "entity_id": "not.is.null",
            "evidence_confidence": (
                f"gte.{MIN_DECISION_CONFIDENCE}"
            ),
            "order": "scored_at.desc",
            "limit": limit * 3,
        }
    )
    rows = request_json(
        "GET",
        f"/rest/v1/prospect_qualifications?{params}",
    ) or []
    return [row for row in rows if isinstance(row, dict)]


def fetch_identity_link(prospect_id: str) -> dict[str, Any] | None:
    params = urllib.parse.urlencode(
        {
            "select": (
                "prospect_id,entity_id,match_method,match_score,active,created_at"
            ),
            "prospect_id": f"eq.{prospect_id}",
            "active": "eq.true",
            "limit": 2,
        }
    )
    rows = request_json(
        "GET",
        f"/rest/v1/prospect_entity_links?{params}",
    ) or []
    links = [row for row in rows if isinstance(row, dict)]
    if len(links) > 1:
        raise OmegaWorkerError("multiple active identity links")
    return links[0] if links else None
def score_exists(row: Mapping[str, Any]) -> bool:
    params = urllib.parse.urlencode(
        {
            "select": "id",
            "entity_type": "eq.company",
            "entity_id": f"eq.{row['entity_id']}",
            "score_type": f"eq.{SCORE_TYPE}",
            "model_key": f"eq.{MODEL_VERSION}",
            "scored_at": f"eq.{row['scored_at']}",
            "limit": 1,
        }
    )
    rows = request_json(
        "GET",
        f"/rest/v1/intelligence_scores?{params}",
    ) or []
    return bool(rows)


def persist_score(row: dict[str, Any]) -> None:
    params = urllib.parse.urlencode(
        {
            "on_conflict": (
                "entity_type,entity_id,score_type,model_key,scored_at"
            )
        }
    )
    request_json(
        "POST",
        f"/rest/v1/intelligence_scores?{params}",
        payload=row,
        prefer="resolution=ignore-duplicates,return=minimal",
    )


def run_omega_cycle(limit: int = 10) -> dict[str, Any]:
    candidates = fetch_omega_candidates(limit)
    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    skipped_existing = 0

    for qualification in candidates:
        prospect_id = _text(qualification.get("prospect_id"))
        try:
            identity_link = fetch_identity_link(prospect_id)
            if not identity_link:
                raise OmegaWorkerError("active identity link missing")
            row = build_omega_score_row(qualification, identity_link)
            if score_exists(row):
                skipped_existing += 1
                continue
            persist_score(row)
            results.append(
                {
                    "prospect_id": prospect_id,
                    "entity_id": row["entity_id"],
                    "score": row["score"],
                    "confidence": row["confidence"],
                    "expected_revenue": row["features"]["expected_revenue"],
                    "expected_gross_profit": (
                        row["features"]["expected_gross_profit"]
                    ),
                }
            )
            if len(results) >= limit:
                break
        except Exception as exc:
            errors.append(
                {
                    "prospect_id": prospect_id,
                    "error": f"{type(exc).__name__}:{str(exc)[:300]}",
                }
            )
    return {
        "schema_version": "omega_projection_cycle.v1",
        "model_version": MODEL_VERSION,
        "ok": not errors,
        "candidates_seen": len(candidates),
        "scores_written": len(results),
        "skipped_existing": skipped_existing,
        "failed": len(errors),
        "results": results,
        "errors": errors,
        "real_data_only": True,
        "recognized_revenue_written": False,
        "payment_actions": False,
        "buyer_allocation_actions": False,
        "finished_at": _now(),
    }
