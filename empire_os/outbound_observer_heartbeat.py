"""Observer heartbeat state for the outbound Ringleader.

The observer writes this only after a completed OBSERVE cycle. A separate watchdog reads
it so observer failure can be detected even when the observer cannot report its own
failure. The heartbeat carries no execution authority.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from typing import Any, Mapping


DEFAULT_OBSERVER_HEARTBEAT_PATH = Path(
    "/srv/empire_os/runtime/outbound/ringleader_observer_heartbeat.json"
)


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


def write_observer_heartbeat(
    result: Mapping[str, Any],
    *,
    path: Path = DEFAULT_OBSERVER_HEARTBEAT_PATH,
    now: datetime | None = None,
) -> dict[str, Any]:
    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if result.get("mutation_authorized") is not False:
        raise RuntimeError("observer_heartbeat_requires_non_mutating_result")

    ringleader = result.get("ringleader")
    ringleader = dict(ringleader) if isinstance(ringleader, Mapping) else {}
    telemetry = ringleader.get("telemetry_sla")
    telemetry = dict(telemetry) if isinstance(telemetry, Mapping) else {}

    payload = {
        "schema_version": "1",
        "source": "outbound_ringleader_observer",
        "observed_at": timestamp.isoformat(),
        "scope_key": str(result.get("scope_key") or ""),
        "mode": str(result.get("mode") or ""),
        "ringleader_posture": ringleader.get("posture"),
        "telemetry_posture": telemetry.get("posture"),
        "mutation_authorized": False,
        "send_authorized": False,
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(tmp, 0o600)
    tmp.replace(path)
    os.chmod(path, 0o600)
    return payload


def evaluate_observer_heartbeat(
    *,
    path: Path = DEFAULT_OBSERVER_HEARTBEAT_PATH,
    now: datetime | None = None,
    max_age_minutes: int = 15,
) -> dict[str, Any]:
    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    max_age = max(1, int(max_age_minutes))

    if not path.exists():
        return {
            "status": "MISSING",
            "path": str(path),
            "age_seconds": None,
            "max_age_minutes": max_age,
            "mutation_authorized": False,
        }

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, PermissionError, json.JSONDecodeError):
        return {
            "status": "INVALID",
            "path": str(path),
            "age_seconds": None,
            "max_age_minutes": max_age,
            "mutation_authorized": False,
        }

    if not isinstance(payload, Mapping):
        return {
            "status": "INVALID",
            "path": str(path),
            "age_seconds": None,
            "max_age_minutes": max_age,
            "mutation_authorized": False,
        }
    if payload.get("mutation_authorized") is not False:
        return {
            "status": "INVALID",
            "path": str(path),
            "age_seconds": None,
            "max_age_minutes": max_age,
            "mutation_authorized": False,
        }

    observed_at = _parse_ts(payload.get("observed_at"))
    if observed_at is None or observed_at > timestamp + timedelta(minutes=5):
        return {
            "status": "INVALID",
            "path": str(path),
            "age_seconds": None,
            "max_age_minutes": max_age,
            "mutation_authorized": False,
        }

    age_seconds = max(0, int((timestamp - observed_at).total_seconds()))
    status = (
        "STALE"
        if age_seconds > max_age * 60
        else "CURRENT"
    )

    return {
        "status": status,
        "path": str(path),
        "observed_at": observed_at.isoformat(),
        "age_seconds": age_seconds,
        "max_age_minutes": max_age,
        "scope_key": payload.get("scope_key"),
        "mode": payload.get("mode"),
        "ringleader_posture": payload.get("ringleader_posture"),
        "telemetry_posture": payload.get("telemetry_posture"),
        "mutation_authorized": False,
    }
