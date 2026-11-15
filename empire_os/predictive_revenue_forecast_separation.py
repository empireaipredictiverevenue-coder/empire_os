"""Read-only forecast versus operational evidence inventory.

This audit never infers customer actuals from generic runtime JSON.
Source-authenticated forecast custody and canonical actual joins are separate
requirements; caller-authored flags do not confer verified revenue.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, date, timezone
from pathlib import Path
import json
import math
import os
import shutil
import subprocess
from typing import Any, Iterator

SCHEMA = "empire.predictive_revenue.forecast_evidence_separation.v1"
PREDICTION_KEYS = ("predicted_revenue_cents", "predicted_cents",
                   "predicted_value_cents", "forecast_revenue_cents",
                   "predicted_value")
IDENTITY_KEYS = ("forecast_ref", "forecast_id", "prediction_id")
ISSUED_KEYS = ("forecast_registered_at", "forecast_generated_at", "issued_at")
ACTUAL_KEYS = ("actual_cents", "recognized_revenue_cents")
LIMIT_BYTES = 12_000_000
MAX_NODES = 100_000


def _stamp(raw: Any) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        result = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return result.astimezone(timezone.utc) if result.tzinfo is not None else None


def _day(raw: Any) -> date | None:
    if not isinstance(raw, str):
        return None
    try:
        result = date.fromisoformat(raw)
    except ValueError:
        return None
    return result if result.isoformat() == raw else None


def _first(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return None


def classify_record(row: dict[str, Any]) -> str:
    """Strong structural classification, not a revenue or identity attestation."""
    if not isinstance(row, dict):
        return "operational"
    amount = _first(row, PREDICTION_KEYS)
    if not (type(amount) in (int, float)
            and math.isfinite(amount) and amount >= 0):
        return "operational"
    # Existing Predictive Cloud V3 registry uses forecast_key, dimension_key,
    # generated_at and predicted_value, not the report-side forecast_ref form.
    # Matching this shape is NOT proof that PostgreSQL rows or RLS exist.
    if "predicted_value" in row:
        key = row.get("forecast_key")
        scope = row.get("dimension_key")
        registered = _stamp(row.get("generated_at"))
        horizon = row.get("horizon_days")
        samples = row.get("sample_count")
        if (isinstance(key, str) and bool(key.strip())
                and isinstance(scope, str) and scope.startswith("tenant:")
                and len(scope) > len("tenant:")
                and registered is not None
                and row.get("metric") == "recognized_revenue_cents"
                and type(horizon) is int and 1 <= horizon <= 365
                and type(samples) is int and samples > 0):
            return "registry_shape_unverified"
        return "forecast_like_incomplete"
    identifier = _first(row, IDENTITY_KEYS)
    issued = _stamp(_first(row, ISSUED_KEYS))
    target = _day(row.get("target_day") or row.get("target_utc_date"))
    horizon = row.get("horizon_days")
    metric = row.get("metric")
    tenant = row.get("tenant_id")
    if (not isinstance(identifier, str) or not identifier.strip()
            or issued is None or target is None
            or type(horizon) is not int or not 1 <= horizon <= 365
            or (target - issued.date()).days != horizon
            or metric not in ("recognized_revenue_cents", "revenue_cents")
            or not isinstance(tenant, str) or not tenant.strip()):
        return "forecast_like_incomplete"
    return "structural_forecast"


def _nodes(value: Any) -> Iterator[dict[str, Any]]:
    pending = [value]
    seen = 0
    while pending and seen < MAX_NODES:
        item = pending.pop()
        seen += 1
        if isinstance(item, dict):
            yield item
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)


def _candidate_paths(runtime: Path) -> tuple[list[Path], str, bool]:
    """Use the existing host ripgrep where available; never silently trust gaps.

    A failed prefilter degrades to the original exhaustive Python scan.
    This is selection only: classification and financial gates are unchanged.
    """
    exe = shutil.which("rg")
    if exe:
        command = [exe, "--files-with-matches", "--null", "--text", "--hidden",
                   "--no-ignore", "--ignore-case", "--no-messages", "-e",
                   "predicted", "-e", "forecast", "--glob", "*.json"]
        for excluded in ("tests", "fixtures", "docs", "control_plane",
                         "predictive_revenue_control", "worker_code"):
            command.extend(("--glob", f"!**/{excluded}/**"))
        command.append(str(runtime))
        try:
            result = subprocess.run(command, capture_output=True, timeout=45,
                                    check=False)
            if result.returncode in (0, 1, 2) and (
                result.returncode != 2 or result.stdout
            ):
                # ripgrep exit 2 commonly indicates some unreadable files.
                # Retain observable matches, but ALWAYS flag the incomplete
                # scan; do not waste ~90s silently falling back and hiding
                # that the original file population was not fully readable.
                incomplete = result.returncode == 2
                return ([Path(os.fsdecode(f)) for f in
                         result.stdout.split(b"\0") if f],
                        "ripgrep_partial" if incomplete else "ripgrep",
                        incomplete)
        except (OSError, subprocess.TimeoutExpired):
            pass
    # Exact fallback; never imply the fast prefilter covered unreadable rows.
    return list(runtime.rglob("*.json")), "python_exhaustive_fallback", True


def _existing_jev_observation(runtime: Path, clock: datetime) -> dict[str, Any]:
    """Reuse the existing Cloud/JEV observer's source contract, not a model.

    Research observations cannot certify forecasts, buyers or accuracy.
    """
    from empire_os.predictive_cloud_core_jev_observer import SOURCES, _read, _recent

    row, digest = _read(runtime.parent, SOURCES["jev"][0])
    valid = bool(
        digest and row.get("schema_version") == SOURCES["jev"][1]
        and row.get("mode") == "OBSERVE"
        and row.get("execution_authority") == "none"
        and _recent(row.get(SOURCES["jev"][2]), clock, 2)
        and row.get("status") == "CLIENT_PAIN_DISCOVERY_OWNER_REVIEW_ONLY"
        and type(row.get("model_calls")) is int and row["model_calls"] == 0
        and row.get("database_writes") is False
        and row.get("crm_writes") is False
    )
    return {
        "research_signal_available": valid,
        "research_source": SOURCES["jev"][0],
        "research_source_digest_sha256": digest if valid else None,
        "model_calls_verified": 0 if valid else None,
        "forecast_or_customer_outcome_authority": False,
        "truth_class": "OBSERVED" if valid else "UNVERIFIED",
    }


def _evidence_decision(report: dict[str, Any], jev: dict[str, Any]) -> dict[str, Any]:
    """Typed evidence-first reasoning; recommendation, never autonomous action.

    This uses EmpireOS's existing decision state vocabulary. No signal is
    transformed into a numerical probability without calibrated labels.
    """
    from empire_os.real_world_decision_intelligence import CandidateType, DecisionState

    reasons: list[str] = []
    if report["fast_prefilter_failed_or_unavailable"] or report["inaccessible_or_oversized_files"]:
        reasons.append("RUNTIME_INVENTORY_COVERAGE_INCOMPLETE")
    if not report["forecast_origin_verified"]:
        reasons.append("ORIGINAL_FORECAST_REGISTRY_NOT_AUTHENTICATED")
    if report["independently_verified_customer_outcome_pairs"] == 0:
        reasons.append("NO_INDEPENDENT_CUSTOMER_OUTCOME_PAIRS")
    if report["original_independent_finance_gaps_not_admitted"]:
        reasons.append("SOURCE_FINANCIAL_PROOFS_NOT_ADMITTED")
    if not jev["research_signal_available"]:
        reasons.append("JEV_RESEARCH_SOURCE_UNAVAILABLE_OR_STALE")
    if "ORIGINAL_FORECAST_REGISTRY_NOT_AUTHENTICATED" in reasons:
        action = "VERIFY_EXISTING_TENANT_BOUND_FORECAST_REGISTRY"
        why = "A timestamped original source must exist before valid backtesting."
    elif "NO_INDEPENDENT_CUSTOMER_OUTCOME_PAIRS" in reasons:
        action = "VERIFY_EXISTING_TENANT_CUSTOMER_OUTCOMES"
        why = "Without mature, financially reconciled actuals, accuracy is unknowable."
    else:
        action = "INDEPENDENTLY_REVIEW_FORECAST_CALIBRATION"
        why = "Use the existing enterprise scorecard and original baseline after source admission."
    return {
        "schema_version": "empire.predictive_revenue.evidence_decision.v1",
        "state": DecisionState.GATHER_EVIDENCE.value,
        "candidate_type": CandidateType.GATHER_EVIDENCE.value,
        "recommended_next_action": action,
        "rationale": why,
        "reason_codes": reasons,
        "forecast_accuracy_confidence": None,
        "calibration_ready": False,
        "assessment": "INSUFFICIENT_INDEPENDENT_LABELLED_CUSTOMER_EVIDENCE",
        "jev_research_signal_available": jev["research_signal_available"],
        "jev_cannot_replace_financial_ground_truth": True,
        "alternatives_considered": [
            "USE_EXISTING_TENANT_REGISTRY_READER",
            "USE_EXISTING_REVENUE_EVENT_AND_DAY_CENSUS_READERS",
            "WAIT_FOR_12_PLUS_MATURE_HORIZON_MATCHED_CUSTOMER_PAIRS",
        ],
        "reasoning_trace_is_deterministic": True,
        "automated_action_executed": False,
        "execution_authority": "none",
    }


def audit_runtime(runtime: Path, *, now: datetime | None = None) -> dict[str, Any]:
    if not runtime.is_dir():
        raise ValueError("runtime directory missing")
    clock = now or datetime.now(timezone.utc)
    counts: Counter[str] = Counter()
    files = 0
    inaccessible = 0
    scanned_nodes = 0
    paths, prefilter, prefilter_failed = _candidate_paths(runtime)
    for path in paths:
        # Existing observer exclusions: no control proofs feeding their own inputs.
        relative = path.relative_to(runtime)
        if any(part in {"tests", "fixtures", "docs", "control_plane",
                        "predictive_revenue_control", "worker_code"}
               for part in relative.parts):
            continue
        try:
            if not path.is_file() or path.stat().st_size > LIMIT_BYTES:
                inaccessible += 1
                continue
            raw = path.read_bytes()
            if b"predicted" not in raw.lower() and b"forecast" not in raw.lower():
                continue
            data = json.loads(raw)
        except (OSError, UnicodeDecodeError, ValueError):
            inaccessible += 1
            continue
        files += 1
        for row in _nodes(data):
            scanned_nodes += 1
            # Only count nodes with an explicit numeric prediction.
            if _first(row, PREDICTION_KEYS) is None:
                continue
            kind = classify_record(row)
            counts[kind] += 1
            if kind in ("structural_forecast", "registry_shape_unverified"):
                # Caller-asserted actuals cannot establish independent custody.
                if _first(row, ACTUAL_KEYS) is not None:
                    counts["structural_forecast_with_claimed_actual"] += 1
    structural = counts["structural_forecast"]
    # Reuse the FIRST-PARTY finance reader for missing original outcome
    # provenance. It reads only source snapshots, never EmpireDB or a bank.
    # Do not derive an authenticated customer actual from this secondary report.
    finance_status = "FINANCE_READINESS_SOURCE_UNAVAILABLE"
    finance_gap_codes: list[str] = []
    try:
        from empire_os.enterprise_finance_evidence_readiness import (
            review_finance_source_readiness,
        )
        finance = review_finance_source_readiness(runtime.parent, as_of=clock)
        requirements = finance.get("independent_finance_evidence_requirements")
        if (finance.get("schema_version") ==
                "empire.enterprise_finance_source_readiness.v1"
                and finance.get("execution_authority") == "none"
                and finance.get("actual_recognised_revenue_independently_verified") is False
                and isinstance(requirements, list)
                and finance.get("required_proofs_not_admitted_count") == len(requirements)):
            codes = [x.get("evidence_gap") for x in requirements
                     if isinstance(x, dict) and
                     x.get("status") == "NO_INDEPENDENT_PROOF_ADMITTED"]
            if len(codes) == len(requirements) and all(
                isinstance(code, str) and len(code) <= 100 for code in codes
            ):
                finance_status = finance["status"]
                finance_gap_codes = codes
    except (ValueError, TypeError, OSError, KeyError, ImportError):
        pass
    # Secondary service reports can describe holds, but cannot act as
    # independent database, tenant or financial signing authorities.
    status_file = runtime / "predictive_cloud" / "status_latest.json"
    try:
        source_status = json.loads(status_file.read_text())
        if type(source_status) is not dict:
            source_status = {}
    except (OSError, UnicodeDecodeError, ValueError):
        source_status = {}
    reported_registry_attestation = (
        source_status.get("original_frozen_forecast_registry_authenticated_by_status")
        if type(source_status.get("original_frozen_forecast_registry_authenticated_by_status")) is bool
        else None
    )
    reported_customer_forecast = (
        source_status.get("customer_forecast_verified")
        if type(source_status.get("customer_forecast_verified")) is bool
        else None
    )
    jev = _existing_jev_observation(runtime, clock)
    report = {
        "schema_version": SCHEMA,
        "generated_at": clock.isoformat(),
        "mode": "OBSERVE",
        "status": "FORECAST_CUSTODY_AND_ACTUALS_UNVERIFIED",
        "scanned_runtime_json_files": files,
        "inaccessible_or_oversized_files": inaccessible,
        "scanned_json_nodes": scanned_nodes,
        "source_prefilter": prefilter,
        "fast_prefilter_failed_or_unavailable": prefilter_failed,
        "source_scan_exhaustive": not prefilter_failed and inaccessible == 0,
        "source_scan_complete_enough_for_absence_claim": False,
        "structural_forecast_records": structural,
        "registry_shaped_unverified_records": counts["registry_shape_unverified"],
        "forecast_like_incomplete_records": counts["forecast_like_incomplete"],
        "reported_registry_authentication_from_status": reported_registry_attestation,
        "reported_customer_forecast_verified_from_status": reported_customer_forecast,
        "registry_table_and_tenant_reader_checked_by_this_audit": False,
        "canonical_customer_outcome_reader_checked_by_this_audit": False,
        "original_finance_source_readiness_status": finance_status,
        "original_independent_finance_gaps_not_admitted": len(finance_gap_codes),
        "original_independent_finance_gap_codes": finance_gap_codes,
        "numeric_prediction_operational_records": counts["operational"],
        "structural_forecasts_with_claimed_actuals":
            counts["structural_forecast_with_claimed_actual"],
        "authenticated_forecast_registry_records": 0,
        "independently_verified_customer_outcome_pairs": 0,
        "calibration_sample_count": 0,
        "forecast_accuracy_measurable": False,
        "forecast_origin_verified": False,
        "tenant_authorization_verified": False,
        "customer_revenue_verified": False,
        "reason": ("Runtime snapshots cannot prove a frozen original forecast "
                   "registry, complete tenant outcomes, or independent source joins."),
        "production_mutation": False,
        "execution_authority": "none",
    }
    report["jev_evidence_observation"] = jev
    report["decision_support"] = _evidence_decision(report, jev)
    return report


def write_report(runtime: Path, output: Path) -> dict[str, Any]:
    result = audit_runtime(runtime)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    temporary.replace(output)
    return result
