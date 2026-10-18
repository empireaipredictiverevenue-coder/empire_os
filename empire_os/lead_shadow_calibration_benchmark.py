"""Shadow-only prequential evaluation of canonical, verified commercial predictions.

Reuse EmpireOS provenance validation and Quant Brier/reliability metrics.
Never fit or promote model weights from research snippets or partial outcomes.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from math import isfinite
import json
import os
from pathlib import Path
import tempfile

from empire_os.outcome_feedback import validate_verified_feedback
from empire_os.predictive_calibration import review_commercial_prediction
from empire_os.quant_brain import brier_score, calibration_bins


def _time(value: str | datetime) -> datetime:
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid evidence timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timezone-aware evidence required")
    return parsed


def evaluate_shadow_calibration(
    memory: Mapping[str, object], *, tenant_id: str | None,
    as_of: str | datetime, min_history: int = 20, min_evaluations: int = 20,
) -> dict:
    """Compare original conversion probabilities against time-safe historical base rates.

    The comparison uses only outcomes available BEFORE each prediction was made.
    Read-only. Input reviews are revalidated from original prediction + feedback.
    """
    now = _time(as_of)
    if (not isinstance(memory, Mapping) or
        memory.get("schema_version") != "empire.economic_memory.v1" or
        memory.get("mode") != "OBSERVE" or
        memory.get("execution_authority") != "none" or
        memory.get("promoted_learning") is not False):
        raise ValueError("unsafe economic memory")
    if type(min_history) is not int or type(min_evaluations) is not int or min_history < 2 or min_evaluations < 2:
        raise ValueError("invalid evaluation thresholds")
    reviews = memory.get("calibration_evidence")
    feedback = memory.get("verified_learning_feedback")
    if not isinstance(reviews, list) or not isinstance(feedback, list):
        raise ValueError("expected explicit review and feedback collections")
    if reviews or feedback:
        if not tenant_id or memory.get("tenant_id") != tenant_id:
            raise ValueError("explicit matching tenant required for outcomes")
    elif tenant_id is not None and memory.get("tenant_id") != tenant_id:
        raise ValueError("tenant mismatch")

    feedback_by_ref = {}
    for row in feedback:
        if not isinstance(row, Mapping):
            raise ValueError("malformed feedback")
        ref = row.get("outcome_ref")
        if not isinstance(ref, str) or not ref or ref in feedback_by_ref:
            raise ValueError("duplicate or missing outcome identity")
        # Even feedback without a paired prediction must pass the original
        # canonical tenant, terminal-label, provenance and time controls.
        validate_verified_feedback(row, tenant_id=tenant_id, as_of=now)
        feedback_by_ref[ref] = row

    seen_predictions = set()
    seen_outcomes = set()
    seen_opportunities = set()
    validated = []
    for row in reviews:
        if not isinstance(row, Mapping) or not isinstance(row.get("prediction"), Mapping) or not isinstance(row.get("feedback"), Mapping):
            raise ValueError("malformed calibration review")
        if row.get("outcome_ref") not in feedback_by_ref or row["feedback"] != feedback_by_ref[row["outcome_ref"]]:
            raise ValueError("review/feedback source mismatch")
        actual = review_commercial_prediction(
            prediction=row["prediction"], feedback=row["feedback"], tenant_id=tenant_id, as_of=now
        )
        if actual != row or actual.get("shadow_only") is not True or actual.get("promoted_learning") is not False:
            raise ValueError("tampered or promoted calibration")
        prediction_ref, outcome_ref, opportunity_key = (
            actual["prediction_ref"], actual["outcome_ref"], actual["opportunity_key"]
        )
        if prediction_ref in seen_predictions or outcome_ref in seen_outcomes or opportunity_key in seen_opportunities:
            raise ValueError("duplicate prediction/outcome/opportunity creates data leakage")
        seen_predictions.add(prediction_ref)
        seen_outcomes.add(outcome_ref)
        seen_opportunities.add(opportunity_key)
        probability = actual["predicted_value"]
        label = actual["actual_value"]
        if type(probability) not in (int, float) or not isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError("invalid probability")
        if type(label) is not int or label not in (0, 1):
            raise ValueError("invalid verified outcome label")
        predicted = _time(actual["predicted_at"])
        available = _time(actual["actual_at"])
        if not predicted < available <= now:
            raise ValueError("outcome unavailable or prior to prediction")
        validated.append((predicted, available, float(probability), label, prediction_ref))

    scored = []
    for predicted, available, probability, label, ref in sorted(validated, key=lambda r: (r[0], r[4])):
        history = [old_label for _, old_available, _, old_label, _ in validated if old_available < predicted]
        if len(history) >= min_history:
            scored.append((probability, sum(history) / len(history), label))

    blockers = []
    unpaired_feedback = len(set(feedback_by_ref) - seen_outcomes)
    if unpaired_feedback:
        blockers.append("verified_outcome_original_prediction_missing")
    if not validated:
        blockers.append("no_canonical_verified_prediction_outcomes")
    if len(scored) < min_evaluations:
        blockers.append("insufficient_temporal_holdout")
    # A score is descriptive even when a threshold is reached. No automatic promotion.
    candidate_metric = brier_score([row[0] for row in scored], [row[2] for row in scored])
    baseline_metric = brier_score([row[1] for row in scored], [row[2] for row in scored])
    adequate = not blockers
    candidate_brier = candidate_metric.get("brier_score")
    baseline_brier = baseline_metric.get("brier_score")
    # Descriptive calibration diagnostics over the SAME prequential holdout;
    # never borrow outcomes that arrived after a prediction was issued.
    delta = None
    relative_delta = None
    bias = None
    event_rate = None
    mean_probability = None
    if adequate and candidate_brier is not None and baseline_brier is not None:
        delta = round(baseline_brier - candidate_brier, 6)
        relative_delta = (
            round(delta / baseline_brier, 6) if baseline_brier > 0 else None
        )
        event_rate = round(sum(row[2] for row in scored) / len(scored), 6)
        mean_probability = round(sum(row[0] for row in scored) / len(scored), 6)
        bias = round(mean_probability - event_rate, 6)
    return {
        "schema_version": "empire.lead_shadow_calibration_benchmark.v1",
        "reviewed_as_of": now.isoformat(),
        "calibration_improvement_brier_absolute": delta,
        "calibration_improvement_brier_relative": relative_delta,
        "holdout_mean_predicted_probability": mean_probability,
        "holdout_verified_event_rate": event_rate,
        "holdout_signed_probability_bias": bias,
        "calibration_metrics_ready": adequate,
        "calibration_metrics_are_descriptive_only": True,
        "outcomes_used_before_prediction": False,
        "mode": "OBSERVE", "execution_authority": "none",
        "tenant_scoped": bool(tenant_id),
        "verified_review_count": len(validated),
        "verified_outcome_feedback_count": len(feedback_by_ref),
        "unpaired_verified_outcome_count": unpaired_feedback,
        "evaluated_prediction_type": "conversion_probability",
        "lead_research_formula_evaluated": False,
        "temporal_holdout_count": len(scored),
        "minimum_prior_outcomes": min_history,
        "minimum_holdout_outcomes": min_evaluations,
        "evaluation_ready": adequate,
        "blockers": blockers,
        "candidate_brier": candidate_metric.get("brier_score"),
        "historical_baseline_brier": baseline_metric.get("brier_score"),
        "candidate_beats_baseline": (
            candidate_metric["brier_score"] < baseline_metric["brier_score"]
            if adequate else None
        ),
        "calibration_diagnostic": (
            calibration_bins([row[0] for row in scored], [row[2] for row in scored], bins=5)
            if len(scored) >= 50 else None
        ),
        "training_performed": False,
        "model_weight_mutation": False,
        "promoted_learning": False,
        "outbound_authorized": False,
        "commercial_activation_authorized": False,
    }


def refresh_shadow_calibration_snapshot(
    repo_root: str | Path, *, tenant_id: str | None, as_of: str | datetime,
    memory: Mapping[str, object] | None = None,
) -> dict:
    """Write a separate OBSERVE-only comparison from canonical Economic Memory.

    Explicit opt-in only. Never changes model weights or Economic Memory.
    """
    root = Path(repo_root).resolve()
    if memory is None:
        source = root / "runtime/economic_memory/latest.json"
        if source.is_symlink() or not source.is_file():
            raise ValueError("canonical Economic Memory snapshot unavailable")
        memory = json.loads(source.read_text(encoding="utf-8"))
    result = evaluate_shadow_calibration(memory, tenant_id=tenant_id, as_of=as_of)
    destination = root / "runtime/lead_intelligence_calibration/shadow_latest.json"
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if destination.is_symlink() or destination.parent.is_symlink():
        raise ValueError("unsafe shadow output path")
    fd, temporary = tempfile.mkstemp(prefix=".shadow_", dir=destination.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return result
