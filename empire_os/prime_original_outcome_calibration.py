"""PRIME shadow calibration gate consuming ORIGINAL verified-outcome contracts.

This review runs only with owner-supplied records. It reuses the existing
commercial verified-learning and Quant Brier implementations. No live EmpireDB
reads, no CRM, no source polling and no model training; source authentication
must occur with the original authenticated Finance/Outcomes owner.

Absence of inputs is NOT an observed zero. No one can convert an NWS event,
permit hypothesis, user-supplied label or monetary projection into an outcome.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from empire_os.commercial_verified_learning_review import (
    review_verified_learning_candidate,
)
from empire_os.prime_prediction_quality import evaluate_prime_prediction_quality

SCHEMA = "empire.prime.original_outcome_calibration_gate.v1"
MIN_SHADOW_SAMPLE_REVIEW_THRESHOLD = 30
MAX_OUTCOME_REVIEWS = 50
_ALLOWED_FIELDS = frozenset({
    "exact_order_id", "feedback", "original_prediction",
})


def _stamp(value: Any) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("aware as_of required")
    return value.astimezone(timezone.utc)


def _uuid(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a canonical UUID")
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError(f"{name} must be a canonical UUID") from exc


def _base() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "NOT_CONNECTED_NOT_A_VERIFIED_ZERO",
        "owner_input_count": None,
        "owner_reviewed_terminal_outcome_count": None,
        "shadow_prediction_pair_count": None,
        "unpaired_outcome_count": None,
        "observed_outcome_wins_in_owner_supplied_samples": None,
        "shadow_brier_score": None,
        "shadow_signed_probability_bias": None,
        "shadow_prediction_quality": None,
        "calibration_cohort_sufficient": False,
        "shadow_minimum_sample_threshold_met": False,
        "statistical_model_calibration_verified": False,
        "source_owner_authenticated_by_this_module": False,
        "original_prediction_provenance_independently_verified": False,
        "cash_receipts_or_revenue_verified_by_this_module": False,
        "beta_posterior_promoted": False,
        "model_weights_modified": False,
        "scenarios_rescored": False,
        "prime_forecasts_promoted": False,
        "scientist_or_reflector_dispatched": False,
        "training_authorized": False,
        "commercial_execution_authorized": False,
        "payments_made": False,
        "database_writes": False,
        "outbound_sent": False,
        "execution_authority": "none",
        "blockers": ["AUTHENTICATED_ORIGINAL_OUTCOME_READER_NOT_CONNECTED"],
    }


def review_prime_outcome_calibration(
    *, owner_outcome_rows: Sequence[Mapping[str, Any]] | None,
    tenant_id: str, as_of: datetime,
) -> dict[str, Any]:
    """Aggregate owner-supplied genuine outcome *claims* for shadow review.

    Input cannot grant authentication; original owner must obtain each
    feedback record via the restricted canonical DB order reader, and match
    exact original pre-outcome prediction in the original decision journal.
    """
    now = _stamp(as_of)
    result = _base()
    if owner_outcome_rows is None:
        return result
    if type(owner_outcome_rows) not in (tuple, list) or len(owner_outcome_rows) > MAX_OUTCOME_REVIEWS:
        raise ValueError("bounded original-owner outcome review cohort required")
    result["owner_input_count"] = len(owner_outcome_rows)
    result["owner_reviewed_terminal_outcome_count"] = 0
    result["shadow_prediction_pair_count"] = 0
    result["unpaired_outcome_count"] = 0
    result["observed_outcome_wins_in_owner_supplied_samples"] = 0
    if not owner_outcome_rows:
        result["status"] = "OWNER_INPUT_EMPTY_NOT_PROOF_OF_ZERO_OUTCOMES"
        result["blockers"] = ["ORIGINAL_OWNER_OUTCOME_COHORT_EMPTY_NOT_VERIFIED_ZERO"]
        return result

    tenant = _uuid(tenant_id, "tenant_id")
    order_ids: set[str] = set()
    outcome_refs: set[str] = set()
    prediction_refs: set[str] = set()
    predictions: list[float] = []
    binary_outcomes: list[int] = []
    for row in owner_outcome_rows:
        if not isinstance(row, Mapping) or set(row) != _ALLOWED_FIELDS:
            raise ValueError("exact original feedback and prediction fields required")
        order = _uuid(row["exact_order_id"], "order")
        feedback = row["feedback"]
        prediction = row["original_prediction"]
        if not isinstance(feedback, Mapping):
            raise ValueError("canonical feedback mapping required")
        if prediction is not None and not isinstance(prediction, Mapping):
            raise ValueError("original prediction mapping or None required")
        if order in order_ids:
            raise ValueError("duplicate canonical fulfilment order")
        order_ids.add(order)
        ref = feedback.get("outcome_ref")
        if not isinstance(ref, str) or ref in outcome_refs:
            raise ValueError("missing or duplicate canonical outcome receipt")
        outcome_refs.add(ref)
        if prediction is not None:
            pref = prediction.get("prediction_ref")
            if not isinstance(pref, str) or pref in prediction_refs:
                raise ValueError("missing or duplicate original prediction identity")
            prediction_refs.add(pref)
        review = review_verified_learning_candidate(
            feedback=feedback, original_prediction=prediction,
            tenant_id=tenant, exact_order_id=order, now=now,
        )
        if (review["schema_version"] != "empire.commercial.verified_learning_review.v1"
                or review["mode"] != "OBSERVE"
                or review["execution_authority"] != "none"
                or review["model_training_authorized"] is not False
                or review["database_writes"] is not False
                or review["outbound_authorized"] is not False
                or review["original_prediction_independently_authenticated_by_this_review"] is not False
                or review["calibration_training_ready"] is not False
                or review["verified_terminal_outcome_count"] != 1):
            raise ValueError("original verified-learning review authority mismatch")
        label = review.get("realized_binary_outcome")
        if type(label) is not int or label not in (0, 1):
            raise ValueError("original terminal binary label required")
        result["observed_outcome_wins_in_owner_supplied_samples"] += label
        if prediction is not None:
            probability = review.get("original_probability")
            if type(probability) not in (int, float) or not 0 <= probability <= 1:
                raise ValueError("original verified-learning probability missing")
            predictions.append(float(probability))
            binary_outcomes.append(label)
        else:
            result["unpaired_outcome_count"] += 1

    result["owner_reviewed_terminal_outcome_count"] = len(order_ids)
    result["shadow_prediction_pair_count"] = len(predictions)
    if predictions:
        quality = evaluate_prime_prediction_quality(predictions, binary_outcomes)
        if quality["sample_count"] != len(predictions) or quality["execution_authority"] != "none":
            raise ValueError("original Quant prediction quality contract mismatch")
        result["shadow_prediction_quality"] = quality
        result["shadow_brier_score"] = quality["brier_score"]
        result["shadow_signed_probability_bias"] = round(
            sum(outcome - prediction for outcome, prediction in zip(
                binary_outcomes, predictions
            )) / len(predictions), 6
        )
    sufficient = len(predictions) >= MIN_SHADOW_SAMPLE_REVIEW_THRESHOLD
    # Passing a sample-size screening threshold is NOT statistical
    # calibration or provenance verification; held even at 50 samples.
    result["shadow_minimum_sample_threshold_met"] = sufficient
    result["status"] = (
        "SHADOW_METRICS_OWNER_AUTHENTICATION_STILL_REQUIRED"
        if sufficient else "SHADOW_COHORT_INSUFFICIENT_UNPROMOTED"
    )
    result["blockers"] = [
        "ORIGINAL_OUTCOME_AND_PREDECISION_PREDICTION_CUSTODY_NOT_ATTESTED",
        "METRICS_NOT_PERMITTED_TO_TRAIN_OR_ACT",
        "STATISTICAL_CALIBRATION_AND_BIAS_VALIDATION_NOT_COMPLETED",
    ] + ([] if sufficient else ["VERIFIED_CALIBRATION_COHORT_TOO_SMALL"])
    return result
