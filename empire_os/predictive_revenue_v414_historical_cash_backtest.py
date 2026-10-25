"""Predictive Revenue V4.14 — bounded, time-ordered CASH backtest rehearsal.

One original EmpireOS, EmpireDB, Smart CRM; this module runs no database,
network, service, spending, revenue-recognition, or model writes. Historical
rows are caller-provided UNVERIFIED claims, not canonical finance evidence.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
from typing import Any
from uuid import UUID
import json

from empire_os.predictive_revenue_v413_canonical_coverage import (
    SCHEMA as V413_SCHEMA, _original_twin_contract,
)
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier

SCHEMA = "empire.predictive_revenue.v414.held_cash_backtest.v1"
MIN_COHORTS, MAX_COHORTS = 12, 240
MAX_MINOR_UNITS = 10**15
FIELDS = frozenset({
    "cohort_ref", "tenant_id", "source_evidence_digest", "currency_code",
    "cohort_start_utc", "forecast_locked_at", "horizon_days",
    "predicted_cash_minor_units", "naive_baseline_cash_minor_units",
    "claimed_cash_minor_units", "outcome_finalized_at", "outcome_source_ref",
})


def _timestamp(value: object) -> datetime:
    if type(value) is not str or len(value) > 40:
        raise ValueError("V414_EXPLICIT_TIMESTAMP_REQUIRED")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError()
    except ValueError:
        raise ValueError("V414_TIMEZONE_AWARE_TIMESTAMP_REQUIRED") from None
    return parsed.astimezone(timezone.utc)


def _amount(value: object, *, allow_none: bool = False) -> int | None:
    if value is None and allow_none:
        return None
    if type(value) is not int or not 0 <= value <= MAX_MINOR_UNITS:
        raise ValueError("V414_INTEGER_MINOR_UNITS_REQUIRED")
    return value


def _ratio_bps(numerator: int, denominator: int) -> int | None:
    if denominator == 0:
        return None
    return int((Decimal(numerator) * 10000 / Decimal(denominator)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP,
    ))


def _metrics(rows: list[tuple[int, int, int]]) -> dict[str, Any]:
    if not rows:
        return {
            "scored_cohorts": 0, "model_absolute_error_minor_units": None,
            "naive_baseline_absolute_error_minor_units": None,
            "model_mae_minor_units": None, "naive_baseline_mae_minor_units": None,
            "model_wape_basis_points": None,
            "naive_baseline_wape_basis_points": None,
            "model_skill_vs_baseline_basis_points": None,
        }
    model = sum(abs(y - estimate) for estimate, naive, y in rows)
    baseline = sum(abs(y - naive) for estimate, naive, y in rows)
    observed_total = sum(y for _, _, y in rows)
    return {
        "scored_cohorts": len(rows),
        "model_absolute_error_minor_units": model,
        "naive_baseline_absolute_error_minor_units": baseline,
        "model_mae_minor_units": _ratio_bps(model, len(rows)*10000),
        "naive_baseline_mae_minor_units": _ratio_bps(baseline, len(rows)*10000),
        "model_wape_basis_points": _ratio_bps(model, observed_total),
        "naive_baseline_wape_basis_points": _ratio_bps(baseline, observed_total),
        "model_skill_vs_baseline_basis_points": _ratio_bps(
            baseline-model, baseline,
        ),
    }


def review_v414_historical_cash_backtest_held(
    *,
    research_twin: dict[str, Any],
    v413_evidence_coverage: dict[str, Any],
    signed_crm_bearer: str,
    crm_verifier: SignedCrmTenantVerifier,
    claimed_historical_cohorts: tuple[Mapping[str, Any], ...],
    as_of: datetime,
) -> dict[str, Any]:
    """Replay held claims with temporal train/test split and no source promotion.

    The CRM bearer must independently pass its original membership check.
    Neither a field saying 'canonical' nor a SHA-256 is financial verification.
    Historical outcome hashes, invoices, ledgers and completeness require a
    separately authenticated owner-controlled DB reader, not caller claims.
    """
    if type(crm_verifier) is not SignedCrmTenantVerifier:
        raise ValueError("V414_ORIGINAL_CRM_VERIFIER_REQUIRED")
    if type(signed_crm_bearer) is not str or not 1 <= len(signed_crm_bearer) <= 4096:
        raise ValueError("V414_SIGNED_CRM_BEARER_REQUIRED")
    if not _original_twin_contract(research_twin):
        raise ValueError("V414_ORIGINAL_NONPROMOTABLE_TWIN_REQUIRED")
    if (
        type(v413_evidence_coverage) is not dict
        or v413_evidence_coverage.get("schema_version") != V413_SCHEMA
        or v413_evidence_coverage.get("mode") != "OBSERVE"
        or v413_evidence_coverage.get("execution_authority") != "none"
        or v413_evidence_coverage.get("simulated_currency") != research_twin["currency_code"]
        or v413_evidence_coverage.get("recognition_vs_cash_metric_mismatch") is not True
        or v413_evidence_coverage.get("event_currency_verified") is not False
        or v413_evidence_coverage.get("revenue_forecast_calibration_eligible") is not False
        or v413_evidence_coverage.get("complete_30_60_90_cohort_census_verified") is not False
        or v413_evidence_coverage.get("actual_revenue_total_cents") is not None
        or v413_evidence_coverage.get("cash_collected_total_cents") is not None
    ):
        raise ValueError("V414_CANONICAL_COVERAGE_HOLD_REQUIRED")
    if type(as_of) is not datetime or as_of.utcoffset() is None:
        raise ValueError("V414_AWARE_CUTOFF_REQUIRED")
    now = as_of.astimezone(timezone.utc)
    if (
        type(claimed_historical_cohorts) is not tuple
        or not MIN_COHORTS <= len(claimed_historical_cohorts) <= MAX_COHORTS
    ):
        raise ValueError("V414_BOUNDED_COHORT_HISTORY_REQUIRED")
    try:
        tenant = crm_verifier.authenticate(signed_crm_bearer)
    except Exception:
        raise ValueError("V414_ACTIVE_ORIGINAL_CRM_MEMBERSHIP_REQUIRED") from None
    if tenant != research_twin["canonical_tenant_id"]:
        raise ValueError("V414_TENANT_BOUNDARY_VIOLATION")

    seen_refs: set[str] = set()
    last_start: datetime | None = None
    scored: list[tuple[int, int, int]] = []
    missing, immature = 0, 0
    target_dates: list[str] = []
    fixed_horizon: int | None = None
    transcript: list[tuple[str, str, str, int, int, int | None]] = []
    for row in claimed_historical_cohorts:
        if type(row) is not dict or set(row) != FIELDS:
            raise ValueError("V414_EXACT_HISTORICAL_CASE_FIELDS_REQUIRED")
        ref = row["cohort_ref"]
        source_ref = row["outcome_source_ref"]
        if (
            type(ref) is not str or not 8 <= len(ref) <= 160
            or not ref.startswith("cohort:") or not ref.isascii()
            or any(c.isspace() for c in ref)
            or ref in seen_refs
        ):
            raise ValueError("V414_BOUNDED_UNIQUE_COHORT_REF_REQUIRED")
        seen_refs.add(ref)
        if (
            row["tenant_id"] != tenant
            or row["source_evidence_digest"] != research_twin["source_evidence_digest"]
            or row["currency_code"] != research_twin["currency_code"]
        ):
            raise ValueError("V414_COHORT_SOURCE_TENANT_CURRENCY_MISMATCH")
        horizon = row["horizon_days"]
        if type(horizon) is not int or horizon not in (30, 60, 90):
            raise ValueError("V414_HORIZON_30_60_90_REQUIRED")
        if fixed_horizon is None:
            fixed_horizon = horizon
        elif horizon != fixed_horizon:
            raise ValueError("V414_MIXED_HORIZON_ERROR")
        start = _timestamp(row["cohort_start_utc"])
        frozen = _timestamp(row["forecast_locked_at"])
        if (
            frozen >= start or start > now
            or (last_start is not None and start <= last_start)
        ):
            raise ValueError("V414_TEMPORAL_LEAKAGE_OR_ORDER")
        last_start = start
        predicted = _amount(row["predicted_cash_minor_units"])
        baseline = _amount(row["naive_baseline_cash_minor_units"])
        actual = _amount(row["claimed_cash_minor_units"], allow_none=True)
        target = start + timedelta(days=horizon)
        target_dates.append(target.date().isoformat())
        completed = row["outcome_finalized_at"]
        if target > now:
            immature += 1
        if actual is None:
            if completed is not None or source_ref is not None:
                raise ValueError("V414_INCOMPLETE_OUTCOME_MUST_REMAIN_UNKNOWN")
            missing += 1
        else:
            if (
                type(source_ref) is not str or not 8 <= len(source_ref) <= 180
                or not source_ref.startswith("claim:") or not source_ref.isascii()
                or any(ch.isspace() for ch in source_ref)
                or type(completed) is not str
            ):
                raise ValueError("V414_EXPLICIT_UNVERIFIED_CASH_PROVENANCE_REQUIRED")
            finalized = _timestamp(completed)
            if finalized <= target or finalized > now:
                raise ValueError("V414_OUTCOME_FINALITY_AFTER_TARGET_REQUIRED")
            scored.append((predicted, baseline, actual))
        transcript.append((
            ref, start.isoformat(), frozen.isoformat(),
            predicted, baseline, actual,
        ))
    if fixed_horizon is None:
        raise ValueError("V414_NO_HORIZON")

    # Chronological 2/3 : 1/3 split over the FIXED selection, not just
    # survivors. Unknown/missing rows can't be silently dropped to improve
    # a favourable score.
    split = len(claimed_historical_cohorts)*2//3
    older: list[tuple[int,int,int]] = []
    newer: list[tuple[int,int,int]] = []
    # Scoring is available for exploration only when every selected
    # cohort has a mature and complete claimed observation.
    complete = (missing == 0 and immature == 0
                and len(scored) == len(claimed_historical_cohorts))
    if complete:
        older = scored[:split]
        newer = scored[split:]
    all_stats = _metrics(scored if complete else [])
    older_stats = _metrics(older)
    newer_stats = _metrics(newer)
    blockers = [
        "CASH_RECEIPTS_NOT_INDEPENDENTLY_READ_FROM_EMPIREDB",
        "FULL_COHORT_DENOMINATOR_NOT_AUTHENTICATED",
        "SOURCE_RIGHTS_UNVERIFIED",
        "HISTORICAL_FORECAST_FREEZE_NOT_AUTHENTICATED",
        "NO_MATCHED_REVERSALS_REFUNDS_OR_SETTLEMENT_FINALITY",
        "NO_VERIFIED_HISTORICAL_BASELINE_SOURCE",
        "NO_PRODUCTION_FORECAST_CALIBRATION_AUTHORITY",
    ]
    if missing:
        blockers.append("MISSING_OUTCOMES_CANNOT_BE_ZERO")
    if immature:
        blockers.append("COHORT_HAS_NOT_REACHED_FORECAST_HORIZON")
    if not complete:
        blockers.append("INCOMPLETE_FIXED_HISTORICAL_SELECTION")
    skill = newer_stats["model_skill_vs_baseline_basis_points"]
    if complete and (skill is None or skill <= 0):
        blockers.append("MODEL_NOT_BETTER_THAN_HISTORICAL_BASELINE")
    digest = sha256(json.dumps(
        transcript, sort_keys=True, separators=(",",":"), allow_nan=False,
    ).encode()).hexdigest()
    return {
        "schema_version": SCHEMA,
        "status": (
            "COMPLETE_CLAIMED_HISTORICAL_SCORECARD_EVIDENCE_HELD"
            if complete else "HISTORICAL_COHORT_COVERAGE_INCOMPLETE_HELD"
        ),
        "mode": "OBSERVE",
        "currency_code": research_twin["currency_code"],
        "cash_metric": "gross_collected_cash_claims_not_finance_verified",
        "horizon_days": fixed_horizon,
        "selected_cohort_count": len(claimed_historical_cohorts),
        "unknown_outcome_count": missing,
        "immature_outcome_count": immature,
        "all_fixed_selection_mature_claims_present": complete,
        "historic_inputs_are_caller_supplied": True,
        "chronological_split_index": split,
        "older_segment": older_stats,
        "held_out_recent_segment": newer_stats,
        "all_observed_claims": all_stats,
        "supplied_input_digest_not_a_database_attestation": digest,
        "blockers": sorted(blockers),
        "p10_p50_p90_empirically_calibrated": False,
        "cash_proof_from_canonical_finance": False,
        "historical_forecast_registry_verified": False,
        "tenant_cohort_completeness_verified": False,
        "actual_revenue_recognized_by_review": False,
        "actual_cash_collected_verified": False,
        "calibration_release_authorized": False,
        "model_updated": False,
        "economic_memory_written": False,
        "outbound_authorized": False,
        "paid_traffic_authorized": False,
        "funds_moved": False,
        "execution_authority": "none",
    }
