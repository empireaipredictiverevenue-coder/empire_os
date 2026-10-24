"""Original PRIME forward commercial prediction journal PRE-FLIGHT.

Pure in-memory, OBSERVE-only consistency gate over ORIGINAL prediction
references and ORIGINAL verified-outcome review contracts. It does not
timestamp, sign, append, authenticate, read or write a durable journal.
No outcomes can be learned from source activity, permits, news or trading.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from math import isfinite
import re
from typing import Any

from empire_os.prime_original_outcome_calibration import (
    MAX_OUTCOME_REVIEWS, review_prime_outcome_calibration,
)
from empire_os.commercial_verified_learning_review import review_verified_learning_candidate
from empire_os.prime_prediction_quality import evaluate_prime_prediction_quality
from empire_os.prime_universal_evidence_fusion import _count_band

SCHEMA = "empire.prime.forward_prediction_journal_shadow.v1"
MAX_PREDICTIONS = 50
RESEARCH_THRESHOLD = 0.5
DECISIONS = frozenset({"PREDICT_POSITIVE", "PREDICT_NEGATIVE", "ABSTAIN"})
FIELDS = frozenset({
    "tenant_id", "prediction_ref", "opportunity_key",
    "prediction_type", "predicted_probability", "predicted_at",
    "journal_recorded_at", "horizon_until", "last_feature_observed_at",
    "feature_lineage_sha256", "model_version_sha256",
    "decision_policy_sha256", "research_decision",
})
HEX = re.compile(r"^[a-f0-9]{64}$")


def _time(value: Any) -> datetime:
    if type(value) is not str or len(value) > 40:
        raise ValueError("aware original timestamp required")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        raise ValueError("invalid original timestamp") from None
    if stamp.utcoffset() != timedelta(0):
        raise ValueError("original timestamp must be UTC")
    return stamp.astimezone(timezone.utc)


def _text(value: Any, name: str) -> str:
    if type(value) is not str or not 1 <= len(value) <= 192 or value != value.strip():
        raise ValueError(name + "_bounded_original_reference_required")
    return value


def _prediction(row: Mapping[str, Any], tenant: str, now: datetime) -> dict[str, Any]:
    if type(row) is not dict or set(row) != FIELDS:
        raise ValueError("exact_original_forward_prediction_fields_required")
    if row["tenant_id"] != tenant:
        raise ValueError("forward_prediction_cross_tenant")
    pref = _text(row["prediction_ref"], "prediction_ref")
    key = _text(row["opportunity_key"], "opportunity_key")
    if row["prediction_type"] != "conversion_probability":
        raise ValueError("separate_trading_and_commercial_prediction_types")
    probability = row["predicted_probability"]
    if (type(probability) not in (int, float) or not isfinite(probability)
        or not 0 <= probability <= 1):
        raise ValueError("bounded_finite_probability_required")
    predicted = _time(row["predicted_at"])
    sealed = _time(row["journal_recorded_at"])
    horizon = _time(row["horizon_until"])
    observed = _time(row["last_feature_observed_at"])
    if not observed <= predicted <= sealed <= now or not sealed < horizon:
        raise ValueError("future_leakage_or_backdated_prediction_window")
    if horizon - predicted > timedelta(days=365):
        raise ValueError("bounded_forward_horizon_required")
    for field in ("feature_lineage_sha256", "model_version_sha256", "decision_policy_sha256"):
        lineage = row[field]
        if type(lineage) is not str or not HEX.fullmatch(lineage):
            raise ValueError(field + "_immutable_digest_required")
    action = row["research_decision"]
    if type(action) is not str or action not in DECISIONS:
        raise ValueError("unknown_original_research_decision")
    if ((action == "PREDICT_POSITIVE" and probability < RESEARCH_THRESHOLD)
        or (action == "PREDICT_NEGATIVE" and probability >= RESEARCH_THRESHOLD)):
        raise ValueError("classification_policy_mismatch")
    return dict(row)


def review_prime_forward_journal(
    *, tenant_id: str, as_of: datetime,
    original_predictions: Sequence[Mapping[str, Any]] | None,
    owner_outcome_rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Match only exact original canonical outcome reviews to prelisted forecasts.

    The historical journal's first-write/independent timestamp remains
    UNVERIFIED, because this is read-only caller input, not a sealed ledger.
    Original outcome owner authentication also remains independently required.
    """
    tenant = _text(tenant_id, "tenant_id")
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("aware review clock required")
    now = as_of.astimezone(timezone.utc)
    if original_predictions is not None and (
        type(original_predictions) not in (list, tuple)
        or len(original_predictions) > MAX_PREDICTIONS
    ):
        raise ValueError("bounded_original_prediction_journal_required")
    if owner_outcome_rows is not None and (
        type(owner_outcome_rows) not in (list, tuple)
        or len(owner_outcome_rows) > MAX_OUTCOME_REVIEWS
    ):
        raise ValueError("bounded_original_outcome_cohort_required")
    if owner_outcome_rows is not None and original_predictions is None:
        raise ValueError("outcomes_cannot_backfill_absent_predeclared_journal")

    journal: dict[str, dict[str, Any]] = {}
    opportunity_keys: set[str] = set()
    for row in original_predictions or ():
        item = _prediction(row, tenant, now)
        if item["prediction_ref"] in journal or item["opportunity_key"] in opportunity_keys:
            raise ValueError("duplicate_prediction_or_opportunity_lookahead")
        journal[item["prediction_ref"]] = item
        opportunity_keys.add(item["opportunity_key"])

    matched: set[str] = set()
    paired: list[tuple[float, int, str]] = []
    action_tp = action_fp = action_fn = action_tn = 0
    abstained_outcomes = 0
    reviewed_financial_wins_with_cost = 0
    supplied_gross_profit_cents = 0
    original_calibration = review_prime_outcome_calibration(
        owner_outcome_rows=owner_outcome_rows, tenant_id=tenant, as_of=now,
    ) if owner_outcome_rows is not None else None
    for row in owner_outcome_rows or ():
        if not isinstance(row, Mapping) or set(row) != {
            "exact_order_id", "feedback", "original_prediction",
        } or not isinstance(row["original_prediction"], Mapping):
            raise ValueError("exact_original_owner_prediction_outcome_required")
        original = row["original_prediction"]
        pref = original.get("prediction_ref")
        if type(pref) is not str or pref not in journal:
            raise ValueError("owner_outcome_not_in_predeclared_journal")
        if pref in matched:
            raise ValueError("duplicated_original_prediction_outcome")
        logged = journal[pref]
        for original_field, journal_field in (
            ("tenant_id", "tenant_id"),
            ("opportunity_key", "opportunity_key"),
            ("prediction_type", "prediction_type"),
            ("predicted_at", "predicted_at"),
            ("horizon_until", "horizon_until"),
        ):
            original_value = original.get(original_field)
            expected = logged[journal_field]
            if original_field in ("predicted_at", "horizon_until"):
                if _time(original_value) != _time(expected):
                    raise ValueError("outcome_not_bound_to_predeclared_journal")
            elif original_value != expected:
                raise ValueError("outcome_not_bound_to_predeclared_journal")
        if (type(original.get("predicted_probability")) not in (int, float)
            or float(original["predicted_probability"]) !=
                float(logged["predicted_probability"])):
            raise ValueError("outcome_not_bound_to_predeclared_probability")
        feedback = row["feedback"]
        if not isinstance(feedback, Mapping):
            raise ValueError("original_owner_feedback_mapping_required")
        # Both the journal's recorded time and original prediction must
        # predate outcome evidence. An untrusted caller could still backdate.
        if not (_time(logged["journal_recorded_at"]) <
                _time(feedback.get("outcome_recorded_at")) <=
                _time(feedback.get("available_at")) <=
                _time(logged["horizon_until"])):
            raise ValueError("noncausal_original_journal_outcome_time")
        reviewed = review_verified_learning_candidate(
            feedback=feedback, original_prediction=original,
            tenant_id=tenant, exact_order_id=row["exact_order_id"], now=now,
        )
        if (reviewed["calibration_metric_computed"] is not True
            or reviewed["original_prediction_independently_authenticated_by_this_review"] is not False
            or reviewed["execution_authority"] != "none"):
            raise ValueError("original_owner_calibration_gate_mismatch")
        label = reviewed["realized_binary_outcome"]
        if type(label) is not int or label not in (0, 1):
            raise ValueError("canonical_binary_terminal_outcome_required")
        matched.add(pref)
        paired.append((float(logged["predicted_probability"]), label, logged["research_decision"]))
        decision = logged["research_decision"]
        if decision == "ABSTAIN":
            abstained_outcomes += 1
        elif decision == "PREDICT_POSITIVE":
            if label == 1:
                action_tp += 1
            else:
                action_fp += 1
        elif label == 1:
            action_fn += 1
        else:
            action_tn += 1
        gross = reviewed["verified_gross_profit_cents"]
        if gross is not None:
            if type(gross) is not int:
                raise ValueError("canonical_gross_profit_cents_required")
            reviewed_financial_wins_with_cost += 1
            supplied_gross_profit_cents += gross

    pending = [x for ref, x in journal.items() if ref not in matched]
    matured_missing = sum(_time(x["horizon_until"]) <= now for x in pending)
    abstain_total = sum(x["research_decision"] == "ABSTAIN" for x in journal.values())
    negative_total = sum(x["research_decision"] == "PREDICT_NEGATIVE" for x in journal.values())
    quality = evaluate_prime_prediction_quality(
        [p for p, _, _ in paired], [label for _, label, _ in paired],
    ) if paired else None
    if quality is not None and (quality["sample_count"] != len(paired)
        or quality["model_promotion_authorized"] is not False):
        raise ValueError("original_prime_quant_quality_contract_mismatch")
    if original_calibration is not None and (
        original_calibration["shadow_prediction_pair_count"] != len(paired)
        or original_calibration["execution_authority"] != "none"
    ):
        raise ValueError("original_prime_outcome_pair_count_mismatch")

    blockers = [
        "ORIGINAL_JOURNAL_FIRST_WRITE_NOT_INDEPENDENTLY_TIMESTAMP_AUTHENTICATED",
        "ORIGINAL_OUTCOME_OWNER_AUTHORITY_NOT_ATTESTED",
        "INDEPENDENT_FORWARD_HOLDOUT_NOT_ESTABLISHED",
        "ECONOMIC_COST_COMPLETENESS_NOT_VERIFIED",
    ]
    if original_predictions is None:
        blockers.append("NO_PREDECLARED_JOURNAL_INPUT_NOT_VERIFIED_ZERO")
    elif not journal:
        blockers.append("EMPTY_JOURNAL_NOT_VERIFIED_ZERO")
    if owner_outcome_rows is None:
        blockers.append("ORIGINAL_OWNER_OUTCOMES_NOT_CONNECTED")
    if matured_missing:
        blockers.append("MATURED_PREDICTIONS_WITH_UNKNOWN_OUTCOMES")
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "SHADOW_RESEARCH_NOT_RELEASE_READY",
        "journal_input_count": len(journal) if original_predictions is not None else None,
        "negative_research_decision_count": negative_total if original_predictions is not None else None,
        "abstained_research_decision_count": abstain_total if original_predictions is not None else None,
        "matched_original_owner_review_count": len(paired) if owner_outcome_rows is not None else None,
        "unresolved_prediction_count": len(pending) if original_predictions is not None else None,
        "matured_unknown_outcome_count": matured_missing if original_predictions is not None else None,
        "shadow_quant_prediction_quality": quality,
        "research_action_confusion_counts": {
            "true_positive": action_tp, "false_positive": action_fp,
            "false_negative": action_fn, "true_negative": action_tn,
            "abstained_with_terminal_outcome": abstained_outcomes,
        } if paired else None,
        "owner_reviewed_financial_wins_with_cost_count": reviewed_financial_wins_with_cost
            if owner_outcome_rows is not None else None,
        "partial_owner_supplied_gross_profit_cents": supplied_gross_profit_cents
            if reviewed_financial_wins_with_cost else None,
        "verified_total_economic_value_cents": None,
        "verified_customer_acquisition_cost_cents": None,
        "verified_economic_roi": None,
        "unmatched_predictions_not_assumed_losses": True,
        "negative_and_abstained_decisions_preserved": True,
        "original_prediction_registry_authenticity_verified": False,
        "canonical_outcome_source_independently_authenticated": False,
        "production_accuracy_verified": False,
        "recognised_revenue_verified_by_this_module": False,
        "model_weights_modified": False,
        "trading_execution_authorized": False,
        "outbound_authorized": False,
        "empiredb_written": False,
        "execution_authority": "none",
        "blockers": blockers,
    }


def summarize_prime_forward_founder(internal_review: Mapping[str, Any]) -> dict[str, Any]:
    """Suppress small cells/metrics before any Founder API output."""
    if (type(internal_review) is not dict
        or internal_review.get("schema_version") != SCHEMA
        or internal_review.get("execution_authority") != "none"
        or internal_review.get("production_accuracy_verified") is not False
        or internal_review.get("original_prediction_registry_authenticity_verified") is not False):
        raise ValueError("original_unpromoted_private_journal_review_required")
    n = internal_review.get("journal_input_count")
    paired = internal_review.get("matched_original_owner_review_count")
    if any(type(x) is not int or not 0 <= x <= MAX_PREDICTIONS for x in (n, paired) if x is not None):
        raise ValueError("bounded_original_journal_counts_required")
    # A research numerical score is withheld even with 30 samples until the
    # source and prediction first-write authority has been independently signed.
    return {
        "schema_version": "empire.prime.founder_forward_prediction_status.v1",
        "mode": "OBSERVE",
        "journal_record_count_band": _count_band(n) if n is not None else None,
        "paired_terminal_review_count_band": _count_band(paired) if paired is not None else None,
        "shadow_precision": None,
        "shadow_accuracy": None,
        "shadow_brier": None,
        "owner_claimed_gross_profit_cents": None,
        "true_economic_value_verified": False,
        "journal_first_write_authenticated": False,
        "original_outcomes_independently_authenticated": False,
        "negative_and_abstained_decisions_preserved": True,
        "matured_unknown_outcomes_not_zero": True,
        "no_forecast_model_promotion": True,
        "original_empiredb_writes": False,
        "execution_authority": "none",
        "status": "FORWARD_JOURNAL_SHADOW_HOLD",
    }
