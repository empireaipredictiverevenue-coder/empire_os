"""Telemetry freshness and blind-spot detection for Empire outbound.

This evaluates observer/source heartbeats, not the presence of email outcomes. A mailbox
can have zero bounces or complaints and still be observable; conversely, "no events" must
never be treated as proof that provider ingestion is healthy.

The result is read-only and cannot authorize sending, provisioning, DNS changes, or
automatic remediation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


def _parse_ts(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def evaluate_telemetry_sla(
    *,
    required_sources: Iterable[str],
    heartbeats: Iterable[Mapping[str, Any]],
    now: datetime | str,
    default_max_age_minutes: int = 30,
    source_max_age_minutes: Mapping[str, int] | None = None,
    critical_sources: Iterable[str] = (),
) -> dict[str, Any]:
    timestamp = (
        now.astimezone(timezone.utc)
        if isinstance(now, datetime)
        else _parse_ts(now)
    )
    if timestamp is None:
        raise ValueError("now_must_be_valid_timestamp")

    required = list(dict.fromkeys(
        str(value or "").strip()
        for value in required_sources
        if str(value or "").strip()
    ))
    critical = {
        str(value or "").strip()
        for value in critical_sources
        if str(value or "").strip()
    }
    age_overrides = {
        str(key): max(1, int(value))
        for key, value in dict(source_max_age_minutes or {}).items()
        if str(key or "").strip()
    }
    default_age = max(1, int(default_max_age_minutes))

    latest: dict[str, dict[str, Any]] = {}
    malformed: list[str] = []

    for raw in heartbeats:
        row = dict(raw)
        source = str(row.get("source") or row.get("source_key") or "").strip()
        if not source:
            malformed.append("heartbeat_source_missing")
            continue

        observed_at = _parse_ts(row.get("observed_at"))
        if observed_at is None:
            malformed.append(f"heartbeat_timestamp_invalid:{source}")
            continue
        if observed_at > timestamp:
            malformed.append(f"heartbeat_timestamp_in_future:{source}")
            continue

        current = latest.get(source)
        current_at = _parse_ts(current.get("observed_at")) if current else None
        if current_at is None or observed_at > current_at:
            latest[source] = {
                **row,
                "source": source,
                "observed_at": observed_at.isoformat(),
            }

    source_status: dict[str, dict[str, Any]] = {}
    missing_sources: list[str] = []
    stale_sources: list[str] = []
    failed_sources: list[str] = []
    partial_sources: list[str] = []

    for source in required:
        row = latest.get(source)
        max_age_minutes = age_overrides.get(source, default_age)
        if row is None:
            missing_sources.append(source)
            source_status[source] = {
                "status": "MISSING",
                "observed_at": None,
                "age_seconds": None,
                "max_age_minutes": max_age_minutes,
                "success": None,
                "coverage": None,
            }
            continue

        observed_at = _parse_ts(row.get("observed_at"))
        age_seconds = max(
            0,
            int((timestamp - observed_at).total_seconds()),
        ) if observed_at is not None else None

        success = row.get("success") is True
        coverage = row.get("coverage")
        coverage_ok = coverage is not False
        stale = (
            age_seconds is None
            or age_seconds > max_age_minutes * 60
        )

        if stale:
            stale_sources.append(source)
            status = "STALE"
        elif not success:
            failed_sources.append(source)
            status = "FAILED"
        elif not coverage_ok:
            partial_sources.append(source)
            status = "PARTIAL"
        else:
            status = "CURRENT"

        source_status[source] = {
            "status": status,
            "observed_at": row.get("observed_at"),
            "age_seconds": age_seconds,
            "max_age_minutes": max_age_minutes,
            "success": success,
            "coverage": coverage,
            "details": dict(row.get("details") or {})
            if isinstance(row.get("details"), Mapping)
            else {},
        }

    critical_missing = sorted(set(missing_sources).intersection(critical))
    critical_stale = sorted(set(stale_sources).intersection(critical))
    critical_failed = sorted(set(failed_sources).intersection(critical))
    critical_partial = sorted(set(partial_sources).intersection(critical))

    # BLIND means a required source is absent or actively failed. STALE means
    # the observer exists but its last successful/fresh heartbeat is too old.
    if missing_sources or failed_sources:
        posture = "BLIND"
    elif stale_sources:
        posture = "STALE"
    elif partial_sources:
        posture = "PARTIAL"
    else:
        posture = "CURRENT"

    critical_blind = bool(critical_missing or critical_failed)
    critical_stale_flag = bool(critical_stale)
    critical_partial_flag = bool(critical_partial)

    return {
        "posture": posture,
        "required_sources": required,
        "critical_sources": sorted(critical),
        "sources": source_status,
        "missing_sources": sorted(missing_sources),
        "stale_sources": sorted(stale_sources),
        "failed_sources": sorted(failed_sources),
        "partial_sources": sorted(partial_sources),
        "critical_missing_sources": critical_missing,
        "critical_stale_sources": critical_stale,
        "critical_failed_sources": critical_failed,
        "critical_partial_sources": critical_partial,
        "critical_blind": critical_blind,
        "critical_stale": critical_stale_flag,
        "critical_partial": critical_partial_flag,
        "malformed_heartbeats": sorted(set(malformed)),
        "mutation_authorized": False,
        "send_authorized": False,
    }
