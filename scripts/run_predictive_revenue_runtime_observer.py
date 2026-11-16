#!/usr/bin/env python3
"""Predictive Revenue OBSERVE: distinguish registered forecasts from research.

Original observer (preserved in git history at 3d564d115) scanned every
runtime JSON file for keyword fragments, then treated buyer/marketing/research
nodes as forecasts. That was not a source-of-truth or an authenticated query.

The source classifier reads ONLY the original authenticated-source preflight.
An explicitly activated private branch invokes the original model with native
tenant-bound census inputs and a separate restricted writer. Default is still
OBSERVE. No runtime-file observation or public forecast request is admitted.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path("/srv/empire_os")
OUT_REL = "runtime/predictive_revenue_control/predictive_revenue_runtime_latest.json"
PREFLIGHT_REL = (
    "runtime/predictive_revenue_control/authenticated_source_preflight_latest.json"
)
PREFLIGHT_SCHEMA = "empire.predictive_revenue.authenticated_source_preflight.v1"
MAX_SOURCE_AGE_SECONDS = 1800
CONTROL_NAMES = (
    "canonical_identity", "conflict_detection", "duplicate_detection",
    "entity_classification", "input_quality", "output_quality", "quarantine",
)
GOVERNANCE = {
    "prediction_mutation": False,
    "db_write": False,
    "outbound": False,
    "action_authority_granted": False,
}


def _load_bounded_preflight(path: Path) -> dict[str, Any] | None:
    """Only local original preflight; refuse symlinks, oversize or malformed."""
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 32768:
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None
    return raw if isinstance(raw, dict) else None


def _utc(raw: Any) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None


def evaluate_original_source(
    source: Mapping[str, Any] | None, *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """A verified transport status is NOT a verified forecast row.

    A positive aggregate source count cannot establish row identity, predicted
    amount, input provenance, or pre-outcome timestamp custody. Never
    synthesize a registered forecast, pass a candidate, or label verified.
    """
    now = now or datetime.now(timezone.utc)
    if now.utcoffset() is None:
        raise ValueError("aware current time required")
    now = now.astimezone(timezone.utc)
    source = source if isinstance(source, Mapping) else {}
    observed = _utc(source.get("generated_at"))
    fresh = bool(
        observed is not None
        and 0 <= (now - observed).total_seconds() <= MAX_SOURCE_AGE_SECONDS
    )
    schema_ok = source.get("schema_version") == PREFLIGHT_SCHEMA
    source_mode_ok = source.get("mode") == "OBSERVE"
    registry_auth = (
        fresh and schema_ok and source_mode_ok
        and source.get("registry_reader_authenticated_session") is True
        and source.get("original_restricted_registry_reader_reused") is True
    )
    count = source.get("registry_scoped_rows_observed")
    count_valid = type(count) is int and 0 <= count <= 100000
    scoped_count = count if registry_auth and count_valid else None

    if not source:
        status = "ORIGINAL_REGISTRY_PREFLIGHT_MISSING"
    elif not schema_ok or not source_mode_ok:
        status = "ORIGINAL_REGISTRY_PREFLIGHT_CONTRACT_INVALID"
    elif not fresh:
        status = "ORIGINAL_REGISTRY_PREFLIGHT_STALE"
    elif not registry_auth or not count_valid:
        status = "ORIGINAL_REGISTRY_READER_UNAUTHENTICATED"
    elif count == 0:
        status = "AUTHENTICATED_REGISTRY_EMPTY_NO_FORECASTS"
    else:
        status = "REGISTERED_ROWS_REQUIRE_CASE_LEVEL_FORECAST_VALIDATION"

    # Previous 1247 matches were nested research fields, not 1247 actual
    # forecast records. A valid source must come through the original private
    # tenant-bound reader with row-by-row issuance and outcome custody.
    return {
        "schema_version": "empire-predictive-revenue-contextual-runtime-v3",
        "generated_at": now.isoformat(),
        "lane": "predictive_revenue",
        "mode": "OBSERVE",
        "status": status,
        "source_scope": "ORIGINAL_TENANT_BOUND_EMPIREDB_REGISTRY_ONLY",
        "classification_contract": "ORIGINAL_AUTHENTICATED_FORECAST_ROW_REQUIRED",
        "source_preflight_artifact": PREFLIGHT_REL,
        "source_preflight_fresh": fresh,
        "original_registry_reader_authenticated": bool(registry_auth),
        "original_registry_scoped_rows_reported": scoped_count,
        "registered_forecast_rows_independently_inspected": False,
        "research_runtime_json_scanned_as_forecast_candidates": False,
        "research_records_released_or_deleted": False,
        "candidate_count": 0,
        "identity_resolved_count": 0,
        "identity_unresolved_count": 0,
        "input_present_count": 0,
        "output_present_count": 0,
        "evidence_present_count": 0,
        "passed_count": 0,
        "quarantined_count": 0,
        "duplicate_identity_count": 0,
        "duplicate_identities": [],
        "conflict_count": 0,
        "conflicts": [],
        "runtime_verified_controls": [],
        "runtime_unverified_controls": list(CONTROL_NAMES),
        "real_forecast_qualifications_verified": False,
        "genuine_forecast_outcome_pairs_verified": False,
        "model_calibration_authorized": False,
        "commercial_authority": "none",
        "execution_authority": "none",
        "governance": dict(GOVERNANCE),
    }


def run(*, root: Path = ROOT, now: datetime | None = None,
        write: bool = True,
        producer_environment: Mapping[str, str] | None = None) -> dict[str, Any]:
    output = root / OUT_REL
    source = _load_bounded_preflight(root / PREFLIGHT_REL)
    report = evaluate_original_source(source, now=now)
    # Existing department-cycle hook remains the sole scheduled entry point.
    # Activation is a separate owner/founder deployment decision. Never use
    # runtime JSON or public request points as observations/credentials.
    env = producer_environment or {}
    if env.get("EMPIRE_PREDICTIVE_NATIVE_SOURCE_ENABLED") == "1":
        from empire_os.predictive_materializer import produce_native_revenue_forecast
        native = produce_native_revenue_forecast(
            tenant_id=env.get("EMPIRE_PREDICTIVE_TENANT_ID", ""),
            census_dsn=env.get("EMPIRE_PREDICTIVE_CENSUS_DSN", ""),
            reader_dsn=env.get("EMPIRE_PREDICTIVE_REGISTRY_READER_DSN", ""),
            writer_dsn=env.get("EMPIRE_PREDICTIVE_REGISTRAR_DSN", "") if write else "",
            registration_enabled=(write and
                env.get("EMPIRE_PREDICTIVE_NATIVE_REGISTRATION_ENABLED") == "1"),
        )
        report["native_producer"] = native
        if (env.get("EMPIRE_PREDICTIVE_TENANT_ID")
                and env.get("EMPIRE_PREDICTIVE_REGISTRY_READER_DSN")
                and env.get("EMPIRE_PREDICTIVE_CENSUS_DSN")):
            from empire_os.predictive_revenue_daily_census import review_native_outcome_readiness
            report["native_outcome_readiness"] = review_native_outcome_readiness(
                tenant_id=env["EMPIRE_PREDICTIVE_TENANT_ID"],
                reader_dsn=env["EMPIRE_PREDICTIVE_REGISTRY_READER_DSN"],
                census_dsn=env["EMPIRE_PREDICTIVE_CENSUS_DSN"],
            )
        # OBSERVE describes the original source classifier, not the optional
        # private producer's authority. Do not conceal possible writes.
        report["governance"]["prediction_mutation"] = native["registration_attempted"]
        report["governance"]["db_write"] = native["registration_commit_state"] in (
            "UNKNOWN", "COMMITTED", "EXACT_RECORD_PRESENT")
    if write:
        # Original output path only; no second scheduler or receipt registry.
        output.parent.mkdir(parents=True, exist_ok=True)
        tmp = output.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        tmp.replace(output)
    return report


if __name__ == "__main__":
    result = run(producer_environment=os.environ)
    print(json.dumps({
        "status": result["status"],
        "candidate_count": result["candidate_count"],
        "quarantined_count": result["quarantined_count"],
        "original_registry_scoped_rows_reported":
            result["original_registry_scoped_rows_reported"],
        "research_runtime_json_scanned_as_forecast_candidates": False,
        "mode": result["mode"],
        "database_writes": result["governance"]["db_write"],
        "native_producer_status": result.get("native_producer", {}).get("status"),
    }, sort_keys=True))
