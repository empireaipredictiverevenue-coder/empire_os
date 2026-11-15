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


def audit_runtime(runtime: Path, *, now: datetime | None = None) -> dict[str, Any]:
    if not runtime.is_dir():
        raise ValueError("runtime directory missing")
    clock = now or datetime.now(timezone.utc)
    counts: Counter[str] = Counter()
    files = 0
    inaccessible = 0
    scanned_nodes = 0
    for path in runtime.rglob("*.json"):
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
    return {
        "schema_version": SCHEMA,
        "generated_at": clock.isoformat(),
        "mode": "OBSERVE",
        "status": "FORECAST_CUSTODY_AND_ACTUALS_UNVERIFIED",
        "scanned_runtime_json_files": files,
        "inaccessible_or_oversized_files": inaccessible,
        "scanned_json_nodes": scanned_nodes,
        "structural_forecast_records": structural,
        "registry_shaped_unverified_records": counts["registry_shape_unverified"],
        "forecast_like_incomplete_records": counts["forecast_like_incomplete"],
        "reported_registry_authentication_from_status": reported_registry_attestation,
        "reported_customer_forecast_verified_from_status": reported_customer_forecast,
        "registry_table_and_tenant_reader_checked_by_this_audit": False,
        "canonical_customer_outcome_reader_checked_by_this_audit": False,
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


def write_report(runtime: Path, output: Path) -> dict[str, Any]:
    result = audit_runtime(runtime)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    temporary.replace(output)
    return result
