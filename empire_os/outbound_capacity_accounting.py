"""Deterministic replay for the append-only outbound capacity ledger."""
from __future__ import annotations

from typing import Any, Iterable, Mapping


def replay_capacity_events(
    events: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    rows = sorted(
        (dict(row) for row in events),
        key=lambda row: (
            str(row.get("recorded_at") or ""),
            str(row.get("id") or ""),
        ),
    )

    limit: int | None = None
    reserved = 0
    consumed = 0
    anomalies: list[str] = []

    for row in rows:
        event = str(row.get("event_type") or "").upper()
        units = max(0, int(row.get("units") or 0))

        if event == "SET_LIMIT":
            value = row.get("capacity_limit")
            if value is None:
                anomalies.append("set_limit_missing_capacity_limit")
                continue
            limit = max(0, int(value))
            if reserved + consumed > limit:
                anomalies.append("capacity_limit_below_committed_usage")

        elif event == "RESERVE":
            reserved += units

        elif event == "CONSUME":
            from_reserved = min(reserved, units)
            reserved -= from_reserved
            consumed += units

        elif event == "RELEASE":
            if units > reserved:
                anomalies.append("release_exceeds_reserved")
            reserved = max(0, reserved - units)

        elif event == "RESET":
            reserved = 0
            consumed = 0

        else:
            anomalies.append("unknown_capacity_event")

    if limit is None:
        remaining = 0
        state = "UNBOUNDED_NOT_ALLOWED"
        anomalies.append("capacity_limit_missing")
    else:
        remaining = max(0, limit - reserved - consumed)
        state = "OVERDRAWN" if reserved + consumed > limit else "READY"

    return {
        "capacity_limit": limit,
        "reserved": reserved,
        "consumed": consumed,
        "remaining": remaining,
        "state": state,
        "anomalies": list(dict.fromkeys(anomalies)),
        "send_authorized": False,
    }
