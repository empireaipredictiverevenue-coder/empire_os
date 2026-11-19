"""Pure, OBSERVE-only evidence history for bounded construction snapshots.

This is a non-canonical research projection. Its hash chain detects accidental
modification when independently anchored; it is NOT a government signature.
No persistence, scanning, cron, database, commercial or outreach authority.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from empire_os.data_exchange_change_intelligence import (
    _observed,
    _validated_preview,
    assess_construction_changes,
)

HISTORY_SCHEMA = "empire.data_exchange.construction_history.v1"
MAX_SNAPSHOTS = 16
MAX_WINDOW = timedelta(days=90)
MAX_SPAN_PER_SNAPSHOT = timedelta(minutes=30)


def _canonical_hash(value: Any) -> str:
    return sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()


def build_construction_history(
    snapshots: Sequence[Mapping[str, Any]],
    *,
    assessed_at: datetime,
) -> dict[str, Any]:
    """Revalidate each historical OBSERVE snapshot at its own capture time.

    Stops on inconsistent/ambiguous evidence; never derives buyer intent.
    Two independent, comparable snapshots are needed to detect a change.
    """
    if assessed_at.tzinfo is None or assessed_at.utcoffset() is None:
        raise ValueError("assessed_at requires timezone")
    now = assessed_at.astimezone(timezone.utc)
    if (
        not isinstance(snapshots, (tuple, list))
        or not 2 <= len(snapshots) <= MAX_SNAPSHOTS
    ):
        raise ValueError("requires 2..16 bounded snapshots")
    previous_time: datetime | None = None
    manifest: list[dict[str, Any]] = []
    windows: list[dict[str, Any]] = []
    prev_chain_hash = "0" * 64
    previous_snapshot = None
    for i, snapshot in enumerate(snapshots):
        if not isinstance(snapshot, Mapping) or not isinstance(
            snapshot.get("records"), list
        ):
            raise ValueError("snapshot format untrusted")
        raw = snapshot["records"]
        if not raw:
            raise ValueError("no authoritative observations in snapshot")
        if any(not isinstance(row, Mapping) for row in raw):
            raise ValueError("invalid row shape in historical snapshot")
        try:
            stamps = [_observed(row) for row in raw]
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            raise ValueError("historical snapshot observation invalid") from exc
        if any(stamp.tzinfo is None or stamp.utcoffset() is None for stamp in stamps):
            raise ValueError("historical snapshot observation requires timezone")
        captured_at = max(stamps)
        if (
            captured_at > now
            or captured_at - min(stamps) > MAX_SPAN_PER_SNAPSHOT
            or (previous_time is not None and captured_at <= previous_time)
        ):
            raise ValueError("source observation chronology invalid")
        if previous_time is not None and captured_at - previous_time > MAX_WINDOW:
            raise ValueError("comparison window exceeds bounded retention")
        # Re-validate at capture time, not present day, so older valid evidence
        # can be assessed after the original source's freshness window.
        _validated_preview(snapshot, captured_at)
        source_hash = _canonical_hash(snapshot)
        chain_hash = _canonical_hash({
            "seq": i,
            "snapshot_sha256": source_hash,
            "previous_sha256": prev_chain_hash,
            "source_observed_at": captured_at.isoformat(),
        })
        manifest.append({
            "sequence": i,
            "record_count": len(raw),
            "source_observed_at": captured_at.isoformat(),
            "snapshot_sha256": source_hash,
            "previous_sha256": prev_chain_hash,
            "chain_sha256": chain_hash,
        })
        if previous_snapshot is not None:
            change = assess_construction_changes(
                previous_snapshot, snapshot, assessed_at=captured_at
            )
            if change["assessment_status"] != "INTERNAL_CHANGE_REVIEW_ONLY":
                # It may be a legitimate coverage gap; never claim a saleable
                # event from a comparison with uncertain entity continuity.
                windows.append({
                    "from_sequence": i - 1,
                    "to_sequence": i,
                    "assessment_status": "HOLD",
                    "holds": change["holds"],
                    "observed_changes": [],
                    "shared_entity_count": change["shared_entity_count"],
                })
            else:
                windows.append({
                    "from_sequence": i - 1,
                    "to_sequence": i,
                    "assessment_status": "INTERNAL_CHANGE_REVIEW_ONLY",
                    "shared_entity_count": change["shared_entity_count"],
                    "newly_observed_in_sample": change["newly_observed_in_sample"],
                    "not_in_later_sample": change["not_in_later_sample"],
                    "observed_changes": change["observed_changes"],
                })
        previous_snapshot = snapshot
        previous_time = captured_at
        prev_chain_hash = chain_hash

    valid_events = [
        event for window in windows
        if window["assessment_status"] == "INTERNAL_CHANGE_REVIEW_ONLY"
        for event in window["observed_changes"]
    ]
    return {
        "schema_version": HISTORY_SCHEMA,
        "mode": "OBSERVE",
        "product": "empire_construction_signals",
        "snapshot_count": len(manifest),
        "snapshot_manifest": manifest,
        "comparison_windows": windows,
        "window_count": len(windows),
        "held_window_count": sum(
            w["assessment_status"] == "HOLD" for w in windows
        ),
        "observed_change_count": len(valid_events),
        "observed_changes": valid_events,
        "latest_chain_sha256": prev_chain_hash,
        "chain_authenticity": "NOT_EXTERNALLY_ANCHORED",
        "source_claim_verification": "NOT_INDEPENDENTLY_VERIFIED",
        "signal_semantics": "SOURCE_RECORD_CHANGES_NOT_BUYER_INTENT",
        "outcome_backtesting_ready": False,
        "customer_delivery_enabled": False,
        "data_resale_authorized": False,
        "outbound_enabled": False,
        "payment_execution": False,
        "production_writes": False,
        "actual_revenue": False,
        "execution_authority": "NONE",
    }
