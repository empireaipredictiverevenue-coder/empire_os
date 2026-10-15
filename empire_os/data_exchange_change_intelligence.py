"""Fail-closed, reproducible construction change intelligence.

Compares TWO trusted-shape OBSERVE previews. A change is a change to a
public-source observation, never a proof of buying intent. This module never
writes to EmpireDB, sends messages, publishes data or authorises resale.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping

from empire_os.data_exchange_construction import (
    DATASET_ID, MAX_RECORDS, REGION, SCHEMA_VERSION, SOURCE_ID,
    build_construction_preview,
)

CHANGE_SCHEMA = "empire.data_exchange.construction_changes.v1"
RECORD_KEYS = frozenset({
    "record_id", "source_id", "dataset_id", "region", "record_type",
    "source_url", "source_observed_at", "signal_class",
    "planning_permission_status", "site_area_hectares", "source_entry_date",
})
SOURCE_FIELDS = RECORD_KEYS - {"signal_class"}
CONTROL_FIELDS = (
    "customer_delivery_enabled", "data_resale_authorized",
    "outbound_enabled", "payment_execution", "production_writes",
    "actual_revenue",
)


def _digest(value: Any) -> str:
    return sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")).hexdigest()


def _observed(row: Mapping[str, Any]) -> datetime:
    return datetime.fromisoformat(row["source_observed_at"]).astimezone(timezone.utc)


def _validated_preview(value: Any, now: datetime) -> dict[str, dict[str, Any]]:
    if not isinstance(value, Mapping):
        raise ValueError("snapshot not an object")
    if (
        value.get("schema_version") != SCHEMA_VERSION
        or value.get("mode") != "OBSERVE"
        or value.get("data_source") != SOURCE_ID
        or value.get("source_dataset") != DATASET_ID
        or value.get("pilot_region") != REGION
        or value.get("execution_authority") != "NONE"
        or any(value.get(key) is not False for key in CONTROL_FIELDS)
    ):
        raise ValueError("snapshot authority or source scope mismatch")
    records = value.get("records")
    if not isinstance(records, list) or len(records) > MAX_RECORDS:
        raise ValueError("snapshot records are unbounded or absent")
    if value.get("dataset_record_count") != len(records):
        raise ValueError("snapshot record count mismatch")
    if any(not isinstance(row, dict) or set(row) != RECORD_KEYS for row in records):
        raise ValueError("snapshot record contains unreviewed fields")
    # Re-run canonical normalisation, source provenance and freshness checks.
    raw_records = [{key: row[key] for key in SOURCE_FIELDS} for row in records]
    rebuilt = build_construction_preview(raw_records, observed_at=now)
    if rebuilt["records"] != sorted(records, key=lambda x: x["record_id"]):
        raise ValueError("snapshot fails independent schema validation")
    if rebuilt["rejected_counts"] or len(rebuilt["records"]) != len(records):
        raise ValueError("snapshot failed canonical provenance validation")
    return {row["record_id"]: row for row in records}


def assess_construction_changes(
    before: Any, after: Any, *, assessed_at: datetime,
) -> dict[str, Any]:
    """Derive deterministic matched-entity changes; no automatic commercial acts.

    Sources must be fetched independently. This comparison provides no
    cryptographic signature of the government feed and no resale authority.
    """
    if assessed_at.tzinfo is None or assessed_at.utcoffset() is None:
        raise ValueError("assessed_at must be timezone aware")
    now = assessed_at.astimezone(timezone.utc)
    earlier = _validated_preview(before, now)
    later = _validated_preview(after, now)
    reasons: list[str] = []
    if not earlier or not later:
        reasons.append("INSUFFICIENT_COMPARABLE_SAMPLES")
    earlier_times = [_observed(row) for row in earlier.values()]
    later_times = [_observed(row) for row in later.values()]
    if earlier_times and later_times and max(later_times) <= max(earlier_times):
        reasons.append("NO_LATER_OBSERVATION")
    same_ids = sorted(earlier.keys() & later.keys())
    if not same_ids:
        reasons.append("NO_SHARED_OBSERVED_ENTITIES")
    if any(_observed(later[key]) <= _observed(earlier[key]) for key in same_ids):
        reasons.append("REPLAY_OR_BACKDATED_ENTITY")
    if reasons:
        return {
            "schema_version": CHANGE_SCHEMA,
            "mode": "OBSERVE",
            "assessment_status": "HOLD",
            "holds": sorted(set(reasons)),
            "observed_changes": [],
            "shared_entity_count": len(same_ids),
            "customer_delivery_enabled": False,
            "data_resale_authorized": False,
            "execution_authority": "NONE",
        }

    events: list[dict[str, Any]] = []
    for key in same_ids:
        a, b = earlier[key], later[key]
        changes = {}
        for field in ("planning_permission_status", "site_area_hectares"):
            if a[field] != b[field]:
                changes[field] = {"previous": a[field], "current": b[field]}
        if not changes:
            continue
        identity = {
            "source": SOURCE_ID, "dataset": DATASET_ID, "record_id": key,
            "from_values": {k: a[k] for k in changes},
            "to_values": {k: b[k] for k in changes},
            "before_observed_at": a["source_observed_at"],
            "after_observed_at": b["source_observed_at"],
        }
        events.append({
            "event_id": _digest(identity),
            "record_id": key,
            "source_url": b["source_url"],
            "before_observed_at": a["source_observed_at"],
            "after_observed_at": b["source_observed_at"],
            "source_changes": changes,
            "signal_class": "OFFICIAL_RECORD_CHANGE_NOT_BUYING_INTENT",
            "priority": (
                "REVIEW" if "planning_permission_status" in changes
                else "CONTEXT"
            ),
            "buyer_intent_verified": False,
            "commercial_outcome_verified": False,
        })
    # Newly sampled / no-longer-sampled entities are NOT created or deleted sites.
    return {
        "schema_version": CHANGE_SCHEMA,
        "mode": "OBSERVE",
        "assessment_status": "INTERNAL_CHANGE_REVIEW_ONLY",
        "holds": [],
        "data_source": SOURCE_ID,
        "source_dataset": DATASET_ID,
        "pilot_region": REGION,
        "shared_entity_count": len(same_ids),
        "newly_observed_in_sample": sorted(later.keys() - earlier.keys()),
        "not_in_later_sample": sorted(earlier.keys() - later.keys()),
        "coverage_warning": (
            "These are changes in the sampled set, not new or deleted projects"
        ),
        "observed_changes": events,
        "observed_change_count": len(events),
        "source_claim_verification": "NOT_INDEPENDENTLY_VERIFIED",
        "customer_delivery_enabled": False,
        "data_resale_authorized": False,
        "outbound_enabled": False,
        "payment_execution": False,
        "production_writes": False,
        "actual_revenue": False,
        "execution_authority": "NONE",
    }
