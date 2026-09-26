"""Read-only buyer-capacity readiness truth for EmpireOS."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from empire_os.buyer_allocation import buyer_activation_decision


def _text(value: Any) -> str:
    return str(value or "").strip()


def _truthy(value: Any) -> bool:
    return bool(value)


def _positive_int(value: Any) -> bool:
    try:
        return int(value or 0) > 0
    except (TypeError, ValueError):
        return False


def summarize_buyer_capacity(
    buyers: Iterable[Mapping[str, Any]],
    *,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    rows = [dict(row) for row in buyers if isinstance(row, Mapping)]
    blockers: Counter[str] = Counter()
    activated = 0

    for row in rows:
        allowed, reason = buyer_activation_decision(row)
        if allowed:
            activated += 1
        else:
            blockers[reason] += 1

    reviewed = sum(bool(row.get("reviewed_at")) for row in rows)
    terms_verified = sum(
        bool(_text(row.get("commercial_terms_source")))
        and bool(_text(row.get("commercial_terms_reference")))
        and bool(row.get("commercial_terms_verified_at"))
        for row in rows
    )
    capacity_verified = sum(
        bool(row.get("capacity_verified_at")) for row in rows
    )
    delivery_verified = sum(
        bool(row.get("delivery_verified_at")) for row in rows
    )
    commercially_activated = sum(
        _text(row.get("commercial_activation_state")).lower() == "activated"
        for row in rows
    )
    active_status = sum(
        _text(row.get("status")).lower() == "active"
        for row in rows
    )
    active_flag = sum(_truthy(row.get("is_active")) for row in rows)
    market_defined = sum(
        bool(_text(row.get("niche"))) and bool(_text(row.get("metro")))
        for row in rows
    )
    delivery_destination = sum(
        bool(_text(row.get("destination_phone")))
        or bool(_text(row.get("webhook_url")))
        for row in rows
    )
    positive_capacity = sum(
        _positive_int(row.get("daily_cap")) for row in rows
    )

    if activated > 0:
        blocker = None
    elif terms_verified == 0:
        blocker = "verified_commercial_terms"
    elif capacity_verified == 0:
        blocker = "verified_buyer_capacity"
    elif delivery_verified == 0:
        blocker = "verified_delivery"
    else:
        blocker = "commercial_activation"

    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("observed_at must include timezone")

    return {
        "schema_version": "empire.buyer_capacity_readiness.v1",
        "observed_at": now.astimezone(timezone.utc).isoformat(),
        "mode": "OBSERVE",
        "buyers_seen": len(rows),
        "status_active": active_status,
        "is_active_true": active_flag,
        "commercially_activated": commercially_activated,
        "reviewed": reviewed,
        "terms_verified": terms_verified,
        "capacity_verified": capacity_verified,
        "delivery_verified": delivery_verified,
        "market_defined": market_defined,
        "delivery_destination_present": delivery_destination,
        "positive_capacity_configured": positive_capacity,
        "fully_activated": activated,
        "activation_blockers": dict(
            sorted(blockers.items(), key=lambda item: (-item[1], item[0]))
        ),
        "highest_priority_blocker": blocker,
        "allocation_ready": activated > 0,
        "allocation_executed": False,
        "payment_action": False,
        "revenue_recognition": False,
        "execution_authority": "none",
    }
