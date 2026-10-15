"""Append-only, evidence-bounded construction observations for existing EmpireDB.

Pure custody planner and DB reader verification. This is the *same*
canonical validated public OBSERVE snapshot used by Data Exchange V14,
not a second business database or an external source of truth. Its
hash chain is a local integrity commitment, NOT government authentication.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence
from empire_os.data_exchange_change_intelligence import _observed, _validated_preview
from empire_os.data_exchange_history import _canonical_hash, build_construction_history

SCHEMA = "empire.data_exchange.observation_custody.v15"
SOURCE = "gb_planning_data"
DATASET = "brownfield-land"
REGION = "north_west_england"
MAX_OBSERVED_RECORDS = 50
MAX_SNAPSHOT_BYTES = 131072
MAX_BOARD_HISTORY = 16
ALLOWED_SNAPSHOT_FIELDS = frozenset({
    "schema_version", "mode", "product", "pilot_region",
    "data_source", "source_dataset", "dataset_record_count",
    "records", "rejected_counts", "rights_review_eligible",
    "rights_holds", "assessment_status", "source_claim_verification",
    "signal_semantics", "customer_delivery_enabled", "data_resale_authorized",
    "outbound_enabled", "payment_execution", "production_writes",
    "actual_revenue", "execution_authority",
})
GENESIS = "0" * 64
MAX_WINDOW = timedelta(days=90)
FIELDS = frozenset({
    "sequence", "schema_version", "source_id", "dataset_id", "region",
    "source_observed_at", "snapshot_sha256", "previous_chain_sha256",
    "chain_sha256", "snapshot_json",
})


class CustodyIntegrityError(ValueError):
    """No commit permitted with insufficient or contradictory source truth."""


def parse_at(value: str) -> datetime:
    if not isinstance(value, str):
        raise CustodyIntegrityError("source observation timestamp required")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise CustodyIntegrityError("source observation timestamp invalid") from None
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise CustodyIntegrityError("source observation timezone required")
    return dt.astimezone(timezone.utc)


def _guard_snapshot(snapshot: Any, *, now: datetime) -> tuple[datetime, str]:
    if not isinstance(snapshot, Mapping):
        raise CustodyIntegrityError("source snapshot not mapping")
    if (
        set(snapshot) != ALLOWED_SNAPSHOT_FIELDS
        or snapshot.get("assessment_status") != "HOLD"
        or snapshot.get("rights_review_eligible") is not False
        or snapshot.get("rights_holds") != ["RIGHTS_REVIEW_MISSING"]
        or snapshot.get("rejected_counts") != {}
        or snapshot.get("source_claim_verification") != "NOT_INDEPENDENTLY_VERIFIED"
        or snapshot.get("signal_semantics") != "development_context_not_buyer_intent"
    ):
        raise CustodyIntegrityError("unreviewed source or rights claims")
    rows = snapshot.get("records")
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_OBSERVED_RECORDS:
        raise CustodyIntegrityError("empty or unbounded source observation")
    try:
        captured = {_observed(item) for item in rows}
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        raise CustodyIntegrityError("source timestamp missing or invalid") from None
    if len(captured) != 1:
        raise CustodyIntegrityError("snapshot combines different observation times")
    timestamp = next(iter(captured))
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise CustodyIntegrityError("source observation timezone missing")
    if timestamp > now:
        raise CustodyIntegrityError("future source observation")
    if (now - timestamp) > MAX_WINDOW:
        raise CustodyIntegrityError("stale source observation")
    try:
        validated = _validated_preview(snapshot, timestamp)
        if not validated or len(validated) != len(rows):
            raise ValueError("invalid source records")
        from json import dumps
        json_size = len(dumps(snapshot, sort_keys=True, allow_nan=False).encode())
    except (TypeError, ValueError, KeyError, OverflowError):
        raise CustodyIntegrityError("untrusted source snapshot") from None
    if json_size > MAX_SNAPSHOT_BYTES:
        raise CustodyIntegrityError("source snapshot exceeds custody bound")
    return timestamp, _canonical_hash(snapshot)


def validate_custody_row(row: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(row, Mapping) or set(row) != FIELDS:
        raise CustodyIntegrityError("custody row shape mismatch")
    if (type(row.get("sequence")) is not int
        or row["sequence"] < 0
        or row["schema_version"] != SCHEMA
        or row["source_id"] != SOURCE
        or row["dataset_id"] != DATASET
        or row["region"] != REGION):
        raise CustodyIntegrityError("custody scope or sequence invalid")
    snapshot = row["snapshot_json"]
    at = parse_at(row["source_observed_at"])
    observed, digest = _guard_snapshot(snapshot, now=at)
    if observed != at or row.get("snapshot_sha256") != digest:
        raise CustodyIntegrityError("stored snapshot digest or time mismatch")
    prev = row.get("previous_chain_sha256")
    if not isinstance(prev, str) or len(prev) != 64 or any(c not in "0123456789abcdef" for c in prev):
        raise CustodyIntegrityError("previous chain hash invalid")
    if row["sequence"] == 0 and prev != GENESIS:
        raise CustodyIntegrityError("genesis hash mismatch")
    expected = _canonical_hash({
        "seq": row["sequence"], "snapshot_sha256": digest,
        "previous_sha256": prev,
        "source_observed_at": at.isoformat(),
    })
    if row.get("chain_sha256") != expected:
        raise CustodyIntegrityError("stored chain commitment mismatch")
    return dict(row)


def plan_custody_append(
    snapshot: Mapping[str, Any], *, previous: Mapping[str, Any] | None,
    assessed_at: datetime,
) -> dict[str, Any]:
    if assessed_at.tzinfo is None or assessed_at.utcoffset() is None:
        raise CustodyIntegrityError("assessment timestamp needs timezone")
    now = assessed_at.astimezone(timezone.utc)
    at, digest = _guard_snapshot(snapshot, now=now)
    if previous is None:
        seq, prev_hash = 0, GENESIS
    else:
        preceding = validate_custody_row(previous)
        prev_at = parse_at(preceding["source_observed_at"])
        if at == prev_at and digest == preceding["snapshot_sha256"]:
            return {
                "mode": "DUPLICATE_EXACT_SNAPSHOT_NO_WRITE",
                "sequence": preceding["sequence"],
                "chain_sha256": preceding["chain_sha256"],
                "source_observed_at": at.isoformat(),
                "written": False,
            }
        if at <= prev_at:
            raise CustodyIntegrityError("non-monotonic or conflicting observation")
        if at - prev_at > MAX_WINDOW:
            raise CustodyIntegrityError("uncomparable source observation gap")
        seq, prev_hash = preceding["sequence"] + 1, preceding["chain_sha256"]
    row = {
        "sequence": seq, "schema_version": SCHEMA,
        "source_id": SOURCE, "dataset_id": DATASET, "region": REGION,
        "source_observed_at": at.isoformat(),
        "snapshot_sha256": digest,
        "previous_chain_sha256": prev_hash,
        "chain_sha256": _canonical_hash({
            "seq": seq, "snapshot_sha256": digest,
            "previous_sha256": prev_hash,
            "source_observed_at": at.isoformat(),
        }),
        "snapshot_json": snapshot,
    }
    validate_custody_row(row)
    return {"mode": "APPEND_REQUIRED", "row": row, "written": False}


def verify_custody_window(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Verify contiguous DB rows; older links outside window remain unverified."""
    if not isinstance(rows, (list, tuple)) or not 1 <= len(rows) <= MAX_BOARD_HISTORY:
        raise CustodyIntegrityError("custody window must have 1..16 rows")
    normalized = [validate_custody_row(row) for row in rows]
    for earlier, later in zip(normalized, normalized[1:]):
        if (later["sequence"] != earlier["sequence"] + 1
            or later["previous_chain_sha256"] != earlier["chain_sha256"]
            or parse_at(later["source_observed_at"]) <= parse_at(earlier["source_observed_at"])):
            raise CustodyIntegrityError("missing or forged custody chain link")
    if normalized[0]["sequence"] == 0 and normalized[0]["previous_chain_sha256"] != GENESIS:
        raise CustodyIntegrityError("custody origin invalid")
    if len(normalized) >= 2:
        now = parse_at(normalized[-1]["source_observed_at"])
        hist = build_construction_history(
            [row["snapshot_json"] for row in normalized], assessed_at=now
        )
        if hist["latest_chain_sha256"] != normalized[-1]["chain_sha256"] and normalized[0]["sequence"] == 0:
            raise CustodyIntegrityError("history and custody anchor mismatch")
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "row_count": len(normalized),
        "first_sequence": normalized[0]["sequence"],
        "last_sequence": normalized[-1]["sequence"],
        "head_chain_sha256": normalized[-1]["chain_sha256"],
        "window_origin_anchored_to_genesis": normalized[0]["sequence"] == 0,
        "hash_link_integrity": "LOCAL_CHAIN_RECOMPUTED",
        "external_anchor_verified": False,
        "customer_delivery_enabled": False,
        "data_resale_authorized": False,
        "execution_authority": "NONE",
    }
