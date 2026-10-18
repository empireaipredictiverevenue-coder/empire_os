"""Validated Predictive Revenue learning readiness over canonical Economic Memory.

The original lead_shadow_calibration_benchmark verifies prediction/outcome
provenance, cohort chronology and Brier against a historical baseline. This
module translates that existing benchmark into a safe founder action brief.
It never fits/promotes a model or invents learning from empty snapshots.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.lead_shadow_calibration_benchmark import evaluate_shadow_calibration

SCHEMA_VERSION = "empire.predictive_learning_readiness.v1"
MAX_MEMORY_BYTES = 2_000_000
MAX_AGE = timedelta(hours=6)
MAX_RECORDS = 500


def _stamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 60:
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    if result.tzinfo is None or result.utcoffset() is None:
        return None
    return result.astimezone(timezone.utc)


def _held(reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "EVIDENCE_HOLD",
        "reason": reason,
        "source_status": "UNAVAILABLE",
        "verified_review_count": None,
        "verified_outcome_feedback_count": None,
        "temporal_holdout_count": None,
        "candidate_brier": None,
        "historical_baseline_brier": None,
        "candidate_beats_baseline": None,
        "improvement_brier_absolute": None,
        "improvement_brier_relative": None,
        "calibration_bias": None,
        "learning_promoted": False,
        "outbound_authorized": False,
        "model_weight_mutation": False,
        "execution_authority": "none",
        "next_evidence_action": "REFRESH_VALIDATED_ECONOMIC_MEMORY",
    }


def review_verified_learning_readiness(
    memory: Mapping[str, Any],
    *,
    tenant_id: str | None,
    as_of: datetime,
    min_history: int = 20,
    min_evaluations: int = 20,
) -> dict[str, Any]:
    """Work only with an explicitly tenant-scoped, validated memory cohort."""
    now = _stamp(as_of.isoformat()) if isinstance(as_of, datetime) else None
    if now is None:
        raise ValueError("timezone-aware as_of required")
    if not isinstance(memory, Mapping):
        return _held("economic_memory_missing")
    if (memory.get("schema_version") != "empire.economic_memory.v1"
            or memory.get("mode") != "OBSERVE"
            or memory.get("execution_authority") != "none"
            or memory.get("promoted_learning") is not False):
        return _held("economic_memory_contract_untrusted")
    if tenant_id is None and memory.get("tenant_id") is not None:
        return _held("TENANT_SCOPE_REQUIRED")
    if tenant_id is not None and (
        not isinstance(tenant_id, str) or not tenant_id.strip()
        or memory.get("tenant_id") != tenant_id
    ):
        return _held("TENANT_SCOPE_MISMATCH")
    reviews = memory.get("calibration_evidence")
    outcomes = memory.get("verified_learning_feedback")
    if (not isinstance(reviews, list) or not isinstance(outcomes, list)
            or len(reviews) > MAX_RECORDS or len(outcomes) > MAX_RECORDS):
        return _held("outcome_cohort_missing_or_over_limit")

    # Every nonempty record is re-validated by the canonical, tenant-specific
    # prequential benchmark. Exceptions preserve the hold, never promote rows.
    try:
        benchmark = evaluate_shadow_calibration(
            memory, tenant_id=tenant_id, as_of=now,
            min_history=min_history, min_evaluations=min_evaluations,
        )
    except (ValueError, KeyError, TypeError):
        return _held("canonical_calibration_validation_failed")
    blockers = benchmark["blockers"]
    ready = benchmark["evaluation_ready"] is True
    if ready:
        next_action = "FOUNDER_REVIEW_CALIBRATION_VS_HISTORICAL_BASELINE"
    elif "verified_outcome_original_prediction_missing" in blockers:
        next_action = "LINK_ORIGINAL_PREDICTION_TO_VERIFIED_OUTCOME"
    elif "no_canonical_verified_prediction_outcomes" in blockers:
        next_action = "OBTAIN_VERIFIED_TERMINAL_COMMERCIAL_OUTCOMES"
    else:
        next_action = "GROW_TIME_SAFE_VERIFIED_OUTCOME_COHORT"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "SHADOW_CALIBRATION_REVIEW_READY" if ready else "INSUFFICIENT_VERIFIED_EVIDENCE",
        "source_status": "CANONICAL_COHORT_REVALIDATED",
        "reason": None if ready else "verified_economic_outcomes_or_holdout_insufficient",
        "tenant_scoped": bool(tenant_id),
        "verified_review_count": benchmark["verified_review_count"],
        "verified_outcome_feedback_count": benchmark["verified_outcome_feedback_count"],
        "temporal_holdout_count": benchmark["temporal_holdout_count"],
        "required_prior_outcomes": benchmark["minimum_prior_outcomes"],
        "required_holdout_outcomes": benchmark["minimum_holdout_outcomes"],
        "candidate_brier": benchmark["candidate_brier"] if ready else None,
        "historical_baseline_brier": (
            benchmark["historical_baseline_brier"] if ready else None
        ),
        "candidate_beats_baseline": benchmark["candidate_beats_baseline"] if ready else None,
        "improvement_brier_absolute": (
            benchmark["calibration_improvement_brier_absolute"] if ready else None
        ),
        "improvement_brier_relative": (
            benchmark["calibration_improvement_brier_relative"] if ready else None
        ),
        "calibration_bias": (
            benchmark["holdout_signed_probability_bias"] if ready else None
        ),
        "blockers": list(blockers),
        "next_evidence_action": next_action,
        "calibration_diagnostic_is_not_revenue_attribution": True,
        "original_outcome_linkage_required": True,
        "historical_baseline_is_temporally_prior": True,
        "learning_promoted": False,
        "outbound_authorized": False,
        "model_weight_mutation": False,
        "commercial_execution": False,
        "execution_authority": "none",
    }


def read_founder_learning_readiness(
    repo_root: str | Path, *, as_of: datetime | None = None,
) -> dict[str, Any]:
    """Safe unscoped founder summary. Never read tenant data into public UI."""
    now = as_of or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("timezone-aware as_of required")
    now = now.astimezone(timezone.utc)
    root = Path(repo_root).resolve(strict=False)
    path = root / "runtime/economic_memory/latest.json"
    try:
        if (path.is_symlink() or path.parent.is_symlink()
                or (root / "runtime").is_symlink() or not path.is_file()):
            return _held("economic_memory_unavailable_or_unsafe")
        size = path.stat().st_size
        if not 0 < size <= MAX_MEMORY_BYTES:
            return _held("economic_memory_size_invalid")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, TypeError):
        return _held("economic_memory_source_unreadable")
    if not isinstance(payload, dict):
        return _held("economic_memory_source_not_object")
    # Don't expose tenant-specific history in a global founder dashboard.
    if payload.get("tenant_id") is not None:
        return _held("TENANT_SCOPE_REQUIRED")
    stamp = _stamp(payload.get("generated_at"))
    if stamp is None:
        return _held("economic_memory_timestamp_missing")
    if stamp > now:
        return _held("economic_memory_timestamp_future")
    if now - stamp > MAX_AGE:
        return _held("economic_memory_stale")
    return review_verified_learning_readiness(
        payload, tenant_id=None, as_of=now,
    )
