"""V16: verifiable historical sample quality for existing EmpireDB custody.

Pure, read-only analysis of canonical V15 rows plus optional fresh official
recheck from SAME government endpoint. No market coverage extrapolation, no
government signature claim, no source-rights clearance, buyer intent or AGI
prediction. This is not a second database, runtime, timer or scanner.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

from empire_os.data_exchange_change_intelligence import _validated_preview
from empire_os.data_exchange_observation_custody import (
    CustodyIntegrityError, _guard_snapshot, parse_at, verify_custody_window,
)
from empire_os.data_exchange_signal_board import build_signal_board

SCHEMA = "empire.data_exchange.temporal_quality.v16"
PILOT_IDS = frozenset({"1722645", "1739516", "1739547"})
MAX_RECENCY = timedelta(hours=72)
MIN_SEPARATION = timedelta(hours=24)
FIELDS = ("planning_permission_status", "site_area_hectares", "source_entry_date")
SOURCE_SCOPE = "THREE_NAMED_ENTITIES_NOT_REGIONAL_MARKET_COVERAGE"


def _fields(snapshot: Mapping[str, Any], timestamp: datetime) -> dict[str, dict[str, Any]]:
    _guard_snapshot(snapshot, now=timestamp)
    canonical = _validated_preview(snapshot, timestamp)
    return {ident: {key: record[key] for key in FIELDS}
            for ident, record in canonical.items()}


def build_temporal_quality(
    rows: Sequence[Mapping[str, Any]], *, assessed_at: datetime,
    recheck: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate canonical history and evaluate bounded repeat-source evidence.

    recheck must be a *separately fetched* official OBSERVE projection, not
    a caller-supplied rights clearance or appended history row. It is only
    same-origin corroboration and never independent source authentication.
    """
    if not isinstance(assessed_at, datetime) or (
        assessed_at.tzinfo is None or assessed_at.utcoffset() is None
    ):
        raise CustodyIntegrityError("quality assessment needs UTC-aware time")
    now = assessed_at.astimezone(timezone.utc)
    proof = verify_custody_window(rows)
    normalized = list(rows)
    latest = normalized[-1]
    observed = parse_at(latest["source_observed_at"])
    if observed > now:
        raise CustodyIntegrityError("future custody head")
    age = now - observed
    latest_fields = _fields(latest["snapshot_json"], observed)
    latest_ids = set(latest_fields)
    if not latest_ids.issubset(PILOT_IDS):
        raise CustodyIntegrityError("custody includes out-of-scope entity")
    scoped_coverage = latest_ids == PILOT_IDS
    has_two = len(normalized) >= 2
    minimum_separation = False
    interval_seconds = None
    if has_two:
        prior = parse_at(normalized[-2]["source_observed_at"])
        separation = observed - prior
        if separation <= timedelta(0):
            raise CustodyIntegrityError("non-monotonic quality interval")
        interval_seconds = int(separation.total_seconds())
        minimum_separation = separation >= MIN_SEPARATION

    recheck_result = "NOT_PERFORMED"
    recheck_at = None
    mismatch_ids: list[str] = []
    mismatch_fields: dict[str, list[str]] = {}
    if recheck is not None:
        recheck_at, _ = _guard_snapshot(recheck, now=now)
        if recheck_at <= observed:
            raise CustodyIntegrityError("recheck must follow stored observation")
        checked = _fields(recheck, recheck_at)
        mismatch_ids = sorted(set(checked) ^ latest_ids)
        mismatch_fields = {
            ident: sorted(k for k in FIELDS
                          if latest_fields[ident][k] != checked[ident][k])
            for ident in sorted(set(checked) & latest_ids)
            if any(latest_fields[ident][k] != checked[ident][k] for k in FIELDS)
        }
        recheck_result = (
            "REPEAT_SAME_SOURCE_MATCH" if not mismatch_ids and not mismatch_fields
            else "RECHECK_DIFFERS_FROM_STORED_SOURCE"
        )

    board_status = "HOLD_NEED_TWO_CANONICAL_OBSERVATIONS"
    observed_changes = 0
    queue_count = 0
    held_comparisons = 0
    coverage_gaps = 0
    if has_two:
        board = build_signal_board(
            source_snapshots=[r["snapshot_json"] for r in normalized],
            procurement=None, assessed_at=now, limit=24,
        )
        if (board["customer_delivery_enabled"] is not False
            or board["source_history_sha256"] != proof["head_chain_sha256"]
            and proof["window_origin_anchored_to_genesis"]):
            raise CustodyIntegrityError("V14 board / V15 canonical head mismatch")
        board_status = board["feed_status"]
        observed_changes = board["total_validated_changes"]
        queue_count = board["queue_count"]
        held_comparisons = board["held_comparison_count"]
        coverage_gaps = board["coverage_gap_count"]

    holds = []
    if not has_two:
        holds.append("SECOND_CANONICAL_OBSERVATION_REQUIRED")
    if has_two and not minimum_separation:
        holds.append("LATEST_OBSERVATIONS_LESS_THAN_24H_APART")
    if age > MAX_RECENCY:
        holds.append("LATEST_CANONICAL_OBSERVATION_OVER_72H_OLD")
    if not scoped_coverage:
        holds.append("PINNED_THREE_ENTITY_SAMPLE_INCOMPLETE")
    if recheck is None:
        holds.append("LIVE_SAME_SOURCE_RECHECK_NOT_PERFORMED")
    elif recheck_result != "REPEAT_SAME_SOURCE_MATCH":
        holds.append("CURRENT_SOURCE_DIFFERS_REQUIRES_NEW_CANONICAL_OBSERVATION")
    if held_comparisons:
        holds.append("HISTORICAL_COMPARISON_WINDOW_HELD")

    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "HOLD_REVIEW_REQUIRED" if holds else "INTERNAL_REVIEW_READY",
        "holds": holds,
        "canonical_observation_count_in_window": len(normalized),
        "canonical_first_sequence": proof["first_sequence"],
        "canonical_head_sequence": proof["last_sequence"],
        "canonical_head_sha256": proof["head_chain_sha256"],
        "hash_link_integrity": proof["hash_link_integrity"],
        "genesis_present_in_window": proof["window_origin_anchored_to_genesis"],
        "external_anchor_verified": False,
        "latest_observed_at": observed.isoformat(),
        "latest_observation_age_seconds": int(age.total_seconds()),
        "latest_interval_seconds": interval_seconds,
        "minimum_24h_separation_met": minimum_separation,
        "pilot_entity_ids_observed": sorted(latest_ids),
        "pilot_entity_count": len(latest_ids),
        "pilot_entity_scope": SOURCE_SCOPE,
        "pinned_sample_fully_observed": scoped_coverage,
        "regional_market_coverage_percent": None,
        "regional_market_universe_verified": False,
        "recheck_at": recheck_at.isoformat() if recheck_at else None,
        "same_source_recheck": recheck_result,
        "recheck_mismatched_entity_ids": mismatch_ids,
        "recheck_mismatched_fields_by_id": mismatch_fields,
        "source_authenticity": "NOT_INDEPENDENTLY_VERIFIED",
        "source_recheck_independent_authority": False,
        "v14_board_status": board_status,
        "observed_source_field_changes": observed_changes,
        "board_review_queue_count": queue_count,
        "held_comparison_count": held_comparisons,
        "sample_membership_gap_count": coverage_gaps,
        "buyer_intent_verified": False,
        "forecast_accuracy_verified": False,
        "independent_field_rights_review": "NOT_COMPLETED",
        "customer_delivery_enabled": False,
        "data_resale_authorized": False,
        "outbound_enabled": False,
        "payment_execution": False,
        "production_writes": False,
        "actual_revenue": False,
        "execution_authority": "NONE",
    }
