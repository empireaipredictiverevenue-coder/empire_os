"""Read-only, bounded first-party buyer capacity evidence for executive review.

Aggregate configured buyers are not verified solar/postcode buy boxes, a
commercial offer, approved lead delivery or realised revenue.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

SCHEMA_VERSION = "empire.executive.buyer_capacity_review.v1"
SOURCE_SCHEMA = "empire.buyer_capacity_readiness.v1"
MAX_AGE = timedelta(hours=4)
COUNT_FIELDS = (
    "buyers_seen", "reviewed", "market_defined",
    "positive_capacity_configured", "delivery_destination_present",
    "capacity_verified", "terms_verified", "delivery_verified",
    "commercially_activated", "fully_activated",
)


def _base(status: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "mode": "OBSERVE",
        "observed_at": None,
        "source_current": False,
        "counts": None,
        "specific_buybox_verified": False,
        "solar_installer_postcode_coverage_verified": False,
        "publisher_payout_can_be_quoted": False,
        "lead_delivery_authorized": False,
        "payment_execution": False,
        "execution_authority": "none",
    }


def review_buyer_capacity(
    source: Mapping[str, Any] | None, *, as_of: datetime,
) -> dict[str, Any]:
    """Validate timestamped aggregates; never upgrade them into buyer terms."""
    if not isinstance(as_of, datetime) or as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("timezone-aware as_of required")
    now = as_of.astimezone(timezone.utc)
    if source is None:
        return _base("SOURCE_MISSING")
    if not isinstance(source, Mapping):
        return _base("SOURCE_UNTRUSTED")
    if (source.get("schema_version") != SOURCE_SCHEMA
            or source.get("mode") != "OBSERVE"
            or source.get("execution_authority") not in ("none", "NONE")
            or source.get("allocation_executed") is not False
            or source.get("allocation_ready") is not False
            or source.get("payment_action") is not False
            or source.get("revenue_recognition") is not False
            or any(type(source.get(key)) is not int or not 0 <= source[key] <= 10_000_000
                   for key in COUNT_FIELDS)):
        return _base("SOURCE_UNTRUSTED")
    seen = source["buyers_seen"]
    if any(source[key] > seen for key in COUNT_FIELDS if key != "buyers_seen"):
        return _base("SOURCE_UNTRUSTED")
    stamp_text = source.get("observed_at")
    if not isinstance(stamp_text, str):
        return _base("SOURCE_UNTRUSTED")
    try:
        stamp = datetime.fromisoformat(stamp_text.replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            return _base("SOURCE_UNTRUSTED")
        stamp = stamp.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return _base("SOURCE_UNTRUSTED")
    if not timedelta(0) <= now - stamp <= MAX_AGE:
        return {**_base("SOURCE_STALE"), "observed_at": stamp.isoformat()}
    counts = {name: source[name] for name in COUNT_FIELDS}
    complete_aggregates = all(source[k] > 0 for k in (
        "capacity_verified", "terms_verified", "delivery_verified",
        "commercially_activated",
    ))
    return {
        **_base("AGGREGATE_CAPACITY_NOT_SPECIFIC_BUYBOX" if complete_aggregates
                else "NO_VERIFIED_COMMERCIAL_CAPACITY"),
        "observed_at": stamp.isoformat(),
        "source_current": True,
        "counts": counts,
    }
