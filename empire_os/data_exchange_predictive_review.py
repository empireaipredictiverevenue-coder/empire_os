"""Strict construction-signal prediction lineage and shadow-only evaluation.

Reuses Empire's canonical verified commercial outcome calibration and Quant
Brier scorer. This reviewer does NOT make forecasts, train models, attribute
sales to a public record, grant licences, publish scores, or recognise revenue.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from empire_os.data_exchange_history import build_construction_history
from empire_os.predictive_calibration import review_commercial_prediction
from empire_os.quant_brain import brier_score

SCHEMA = "empire.data_exchange.predictive_shadow_review.v1"
PRODUCT = "empire_construction_signals"
MIN_COHORT = 20
MAX_COHORT = 100


def _time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("time required as timestamp")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid prediction timestamp") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("prediction timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc)


def review_construction_prediction_cohort(
    *,
    source_snapshots: Sequence[Mapping[str, Any]],
    pairs: Sequence[Mapping[str, Any]],
    tenant_id: str,
    assessed_at: datetime,
) -> dict[str, Any]:
    """Read-only validation: source transition -> prior forecast -> outcome.

    Outputs descriptive diagnostics only. Source causation, buyer intent,
    predictive accuracy claims and model promotion require separate review.
    """
    if (
        assessed_at.tzinfo is None or assessed_at.utcoffset() is None
        or not isinstance(tenant_id, str) or not tenant_id.strip()
    ):
        raise ValueError("tenant and timezone scope required")
    now = assessed_at.astimezone(timezone.utc)
    history = build_construction_history(source_snapshots, assessed_at=now)
    events = history["observed_changes"]
    index = {e["event_id"]: e for e in events}
    if len(index) != len(events):
        raise ValueError("non-unique construction source events")
    if not isinstance(pairs, (tuple, list)) or len(pairs) > MAX_COHORT:
        raise ValueError("cohort unbounded or not a sequence")

    unique_predictions: set[str] = set()
    unique_outcomes: set[str] = set()
    predictions: list[float] = []
    outcomes: list[int] = []
    links: list[dict[str, Any]] = []

    for pair in pairs:
        if not isinstance(pair, Mapping) or set(pair) != {"prediction", "feedback"}:
            raise ValueError("untrusted prediction/outcome pair")
        prediction, feedback = pair["prediction"], pair["feedback"]
        if not isinstance(prediction, Mapping) or not isinstance(feedback, Mapping):
            raise ValueError("prediction/feedback must be mappings")
        if prediction.get("data_product") != PRODUCT:
            raise ValueError("wrong construction product")
        event_id = prediction.get("source_event_id")
        if not isinstance(event_id, str) or event_id not in index:
            raise ValueError("forecast source event has no historical evidence")
        event = index[event_id]
        predicted_at = _time(prediction.get("predicted_at"))
        horizon_until = _time(prediction.get("horizon_until"))
        if not _time(event["after_observed_at"]) <= predicted_at < horizon_until <= now:
            raise ValueError("prediction must follow the signal and be fully matured")
        expected_ref = "empire:construction_change:" + event_id
        refs = prediction.get("evidence_refs")
        if not isinstance(refs, (tuple, list)) or expected_ref not in refs:
            raise ValueError("forecast missing attributable source lineage")
        result = review_commercial_prediction(
            prediction=prediction,
            feedback=feedback,
            tenant_id=tenant_id,
            as_of=now,
        )
        if (
            result.get("shadow_only") is not True
            or result.get("calibration_ready") is not True
            or result.get("promoted_learning") is not False
            or result.get("execution_authority") != "none"
        ):
            raise ValueError("canonical calibration not strictly shadow-only")
        forecast_ref, outcome_ref = result["prediction_ref"], result["outcome_ref"]
        if forecast_ref in unique_predictions or outcome_ref in unique_outcomes:
            raise ValueError("duplicate forecast or outcome evidence")
        unique_predictions.add(forecast_ref)
        unique_outcomes.add(outcome_ref)
        predictions.append(result["predicted_value"])
        outcomes.append(result["actual_value"])
        links.append({
            "prediction_ref": forecast_ref,
            "outcome_ref": outcome_ref,
            "source_event_id": event_id,
            "predicted_at": result["predicted_at"],
            "outcome_available_at": result["actual_at"],
            "descriptive_brier": result["brier_score"],
            "verified_commercial_outcome": True,
            "source_causation_established": False,
        })

    blockers = []
    if not index:
        blockers.append("NO_OBSERVED_SOURCE_CHANGES")
    if not pairs:
        blockers.append("NO_CANONICAL_FORECAST_OUTCOME_PAIRS")
    if len(pairs) < MIN_COHORT:
        blockers.append("INSUFFICIENT_VERIFIED_EVALUATION_COHORT")
    if 0 not in outcomes or 1 not in outcomes:
        blockers.append("OUTCOME_CLASS_COVERAGE_MISSING")
    aggregate = brier_score(predictions, outcomes) if predictions else {
        "available": False, "reason": "no_samples", "sample_count": 0,
    }
    # Even a sufficiently large cohort is descriptive, not causal or an
    # independent holdout: model training cutoff and prediction provenance
    # must be reviewed separately before external claims.
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "product": PRODUCT,
        "review_status": "SHADOW_EVIDENCE_ONLY" if not blockers else "HOLD",
        "blockers": sorted(blockers),
        "source_observed_change_count": len(index),
        "history_chain_sha256": history["latest_chain_sha256"],
        "history_chain_authenticity": "NOT_EXTERNALLY_ANCHORED",
        "reviewed_prediction_count": len(links),
        "shadow_calibration": aggregate,
        "prediction_lineage": links,
        "holdout_verified": False,
        "source_causation_established": False,
        "predictive_marketing_claim_ready": False,
        "buyer_intent_verified_by_source": False,
        "model_mutation": False,
        "customer_delivery_enabled": False,
        "data_resale_authorized": False,
        "production_writes": False,
        "outbound_enabled": False,
        "payment_execution": False,
        "actual_revenue_created": False,
        "execution_authority": "NONE",
    }
