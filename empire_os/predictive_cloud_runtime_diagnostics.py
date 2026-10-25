"""Fail-closed, read-only host diagnostics for the existing Predictive Cloud.

These measurements are not economic evidence, inference results or authority
to restart services. Missing instrumentation is explicitly UNKNOWN.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Mapping

SCHEMA = "empire.predictive_cloud.runtime_diagnostics.v1"
SOURCE_CONTRACTS = {
    "cloud": ("empire.predictive_cloud.status.v2", "generated_at", 86400),
    "predictive": ("empire.predictive_intelligence.v1", "generated_at", 86400),
    "jev": ("empire.jev.client_pain_production_observe.v1", "generated_at_utc", 172800),
}
SYSTEMD_KEYS = {
    "Result", "ExecMainStatus", "ExecMainStartTimestamp", "ExecMainExitTimestamp"
}
UNKNOWN_METRICS = (
    "historical_materializer_success_failure_counts",
    "true_source_ingestion_lag",
    "queue_backlogs",
    "postgresql_capacity",
    "inference_request_latency",
    "event_source_failure_rates",
    "model_evaluation_throughput",
)


def _timestamp(value: object, now: datetime) -> int | None:
    if type(value) is not str or len(value) > 48:
        return None
    try:
        if value.endswith(" UTC"):
            parsed = datetime.strptime(value, "%a %Y-%m-%d %H:%M:%S UTC")
            parsed = parsed.replace(tzinfo=timezone.utc)
        else:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.utcoffset() is None:
            return None
        delta = (now - parsed.astimezone(timezone.utc)).total_seconds()
        return int(delta) if 0 <= delta <= 30 * 86400 else None
    except (ValueError, OverflowError):
        return None


def _systemd_show(raw: object) -> dict[str, str]:
    if type(raw) is not str or len(raw) > 8192:
        return {}
    values: dict[str, str] = {}
    for line in raw.splitlines():
        if "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name not in SYSTEMD_KEYS or name in values or len(value) > 128:
            return {}
        values[name] = value
    return values


def _memory(raw: object) -> dict[str, int] | None:
    if type(raw) is not str or len(raw) > 16384:
        return None
    values: dict[str, int] = {}
    for key in ("MemTotal", "MemAvailable"):
        matches = re.findall(r"^" + key + r":\s+(\d+) kB\s*$", raw, re.M)
        if len(matches) != 1:
            return None
        values[key] = int(matches[0]) * 1024
    total, available = values["MemTotal"], values["MemAvailable"]
    if total <= 0 or available > total:
        return None
    return {"total_bytes": total, "available_bytes": available,
            "used_pct": round(100 * (total - available) / total, 1)}


def _disk(disk: object) -> dict[str, int | float] | None:
    if type(disk) is not dict or set(disk) != {"total", "used", "free"}:
        return None
    total, used, free = disk["total"], disk["used"], disk["free"]
    if not all(type(v) is int and v >= 0 for v in (total, used, free)):
        return None
    if not total or used + free > total:
        return None
    return {"total_bytes": total, "available_bytes": free,
            "used_pct": round(100 * used / total, 1)}


def inspect_runtime_diagnostics(*, now: datetime, systemd_show: str,
                                meminfo: str, disk: dict[str, int],
                                snapshots: Mapping[str, Any],
                                load_one: float | None = None,
                                cpu_count: int | None = None) -> dict[str, Any]:
    """Pure calculation over caller-supplied read-only observations."""
    if type(now) is not datetime or now.utcoffset() is None:
        raise ValueError("EXPLICIT_AWARE_CLOCK_REQUIRED")
    if type(snapshots) is not dict or set(snapshots) != set(SOURCE_CONTRACTS):
        raise ValueError("EXACT_SNAPSHOT_CONTRACT_REQUIRED")
    now = now.astimezone(timezone.utc)
    show = _systemd_show(systemd_show)
    result = show.get("Result")
    status_raw = show.get("ExecMainStatus")
    start_age = _timestamp(show.get("ExecMainStartTimestamp"), now)
    exit_age = _timestamp(show.get("ExecMainExitTimestamp"), now)
    valid_run_times = (start_age is not None and exit_age is not None
                       and exit_age <= start_age and start_age <= 7 * 86400)
    status = "UNKNOWN"
    duration = None
    if valid_run_times:
        duration = (start_age - exit_age) * 1000
        if result == "success" and status_raw == "0":
            status = "LAST_RUN_SUCCESS"
        elif result not in (None, "", "success") or (
                status_raw is not None and status_raw.isdecimal()
                and int(status_raw) != 0):
            status = "LAST_RUN_FAILED"
    memory = _memory(meminfo)
    disk_metrics = _disk(disk)
    if (type(load_one) not in (int, float) or
            not (0 <= load_one <= 1_000_000) or
            type(cpu_count) is not int or not 1 <= cpu_count <= 4096):
        normalized_load = None
    else:
        normalized_load = round(load_one / cpu_count, 3)
    source_age: dict[str, int | None] = {}
    blockers: list[str] = []
    for key, (schema, clock, limit) in SOURCE_CONTRACTS.items():
        obj = snapshots[key]
        age = None
        if (type(obj) is dict and obj.get("schema_version") == schema
                and obj.get("mode") == "OBSERVE"
                and obj.get("execution_authority") == "none"):
            age = _timestamp(obj.get(clock), now)
        source_age[key] = age
        if age is None or age > limit:
            blockers.append(key.upper() + "_SNAPSHOT_STALE_OR_UNTRUSTED")
    if status != "LAST_RUN_SUCCESS":
        blockers.append("MATERIALIZER_LAST_RUN_NOT_VERIFIED_SUCCESS")
    if memory is None:
        blockers.append("MEMORY_TELEMETRY_UNKNOWN")
    elif memory["used_pct"] >= 90:
        blockers.append("MEMORY_PRESSURE_HIGH")
    if disk_metrics is None:
        blockers.append("DISK_TELEMETRY_UNKNOWN")
    elif disk_metrics["used_pct"] >= 90:
        blockers.append("DISK_PRESSURE_HIGH")
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "BOUNDED_HOST_DIAGNOSTICS_PARTIAL_COVERAGE",
        "source_snapshot_age_seconds": source_age,
        "materializer_last_run": {"status": status, "duration_ms": duration},
        "system_memory": memory,
        "repo_filesystem": disk_metrics,
        "system_load_1m_per_core": normalized_load,
        "not_instrumented": list(UNKNOWN_METRICS),
        "blockers": sorted(blockers),
        "historical_run_counts": None,
        "revenue_verified": False,
        "model_training_authorized": False,
        "payment_authorized": False,
        "outbound_authorized": False,
        "database_writes": False,
        "service_restarts": 0,
        "external_model_calls": 0,
        "execution_authority": "none",
    }
