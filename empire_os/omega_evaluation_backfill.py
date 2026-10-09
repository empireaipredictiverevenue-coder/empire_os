"""Fail-closed, read-only planning for legacy Omega score enrichment.

No persistence or backfill authority. Existing score identity and model outputs
are immutable; only missing presentation fields can be proposed.
"""
from __future__ import annotations

from typing import Any, Mapping

from empire_os.omega_evaluation import evaluate


class BackfillConflict(ValueError):
    """An existing projection disagrees with the proposed evaluation."""


def plan_enrichment(score: Mapping[str, Any], input_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Plan additive presentation metadata for one verified Omega 2 score."""
    from empire_os.intelligence.omega import MODEL_VERSION

    if score.get("score_type") != "omega_opportunity" or score.get("model_key") != MODEL_VERSION:
        raise BackfillConflict("unsupported score identity or model")
    if not all(score.get(k) for k in ("entity_id", "scored_at")):
        raise BackfillConflict("score identity incomplete")
    if not isinstance(score.get("features"), Mapping) or not isinstance(score.get("explanation"), Mapping):
        raise BackfillConflict("score payload missing")
    result = evaluate(input_snapshot)
    if not isinstance(score.get("score"), (int, float)) or abs(score["score"] - result["score"]) > 0.01:
        raise BackfillConflict("score differs from current Omega model; no automatic migration")
    features = score["features"]
    explanation = score["explanation"]
    additions = {
        "evaluation_schema_version": result["schema_version"],
        "evaluation_grade": result["grade"],
        "evaluation_evidence_coverage": result["legacy_eight_domain_evidence"],
    }
    explanation_additions = {"evaluation_only": True, "value_meter": result["value_meter"]}
    for key, value in additions.items():
        if key in features and features[key] != value:
            raise BackfillConflict(f"conflicting feature: {key}")
    for key, value in explanation_additions.items():
        if key in explanation and explanation[key] != value:
            raise BackfillConflict(f"conflicting explanation: {key}")
    return {
        "schema_version": "empire.omega-evaluation-backfill-plan.v1",
        "entity_id": score["entity_id"],
        "scored_at": score["scored_at"],
        "needs_enrichment": any(key not in features for key in additions) or any(key not in explanation for key in explanation_additions),
        "feature_additions": {k: v for k, v in additions.items() if k not in features},
        "explanation_additions": {k: v for k, v in explanation_additions.items() if k not in explanation},
        "execution_authority": "none",
        "database_write_authorized": False,
    }
