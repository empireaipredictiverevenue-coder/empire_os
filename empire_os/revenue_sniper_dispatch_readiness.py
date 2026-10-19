"""Cross-check three EXISTING EmpireOS read-only commercial snapshots.

A narrowly scoped human-decision dashboard: fresh scanner research,
independent buyer review-readiness and EmpireDB commercial Exchange.

No cross-population record linkage is inferred. No database changes, HTTP
fetches, contact extraction, emails, subscriber change or timer creation.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from empire_os.revenue_sniper_scanner_review import review_existing_scout_snapshot

SCHEMA = "empire.revenue_sniper_dispatch_readiness.v1"
MAX_STALE_HOURS = 6
MAX_CLOCK_SKEW_MINUTES = 5


def _fresh_timestamp(value: Any, now: datetime) -> bool:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return False
        delta = (now - dt).total_seconds()
        return -MAX_CLOCK_SKEW_MINUTES * 60 <= delta <= MAX_STALE_HOURS * 3600
    except (ValueError, TypeError, OverflowError):
        return False


def _safe_int(data: Mapping, key: str) -> int | None:
    number = data.get(key)
    return number if type(number) is int and number >= 0 else None


def build_sniper_dispatch_readiness(
    *,
    scout_snapshot: Mapping,
    buyer_review_snapshot: Mapping,
    commercial_exchange_snapshot: Mapping,
    now: datetime | None = None,
) -> dict:
    """Validate identities of *snapshots*, then plan safe next internal work."""
    if not all(isinstance(x, Mapping) for x in (
        scout_snapshot, buyer_review_snapshot, commercial_exchange_snapshot
    )):
        raise TypeError("all snapshots must be mappings")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone aware")

    sniper = review_existing_scout_snapshot(scout_snapshot, now=current)
    buyer_schema = buyer_review_snapshot.get("schema_version")
    exchange_schema = commercial_exchange_snapshot.get("schema_version")
    review_valid = (
        buyer_schema == "empire.buyer_scout_review_readiness.v1"
        and buyer_review_snapshot.get("mode") == "OBSERVE"
        and buyer_review_snapshot.get("outbound_sent") is False
        and buyer_review_snapshot.get("canonical_promotion_performed") is False
        and buyer_review_snapshot.get("database_write_performed") is False
        and buyer_review_snapshot.get("execution_authority") == "none"
    )
    exchange_valid = (
        exchange_schema == "empire.commercial_exchange_snapshot.v1"
        and commercial_exchange_snapshot.get("mode") == "OBSERVE"
        and commercial_exchange_snapshot.get("execution_authority") == "none"
        and commercial_exchange_snapshot.get("source") == "canonical_empiredb_projection"
        and commercial_exchange_snapshot.get("canonical_backend") == "empiredb"
        and commercial_exchange_snapshot.get("automatic_external_delivery") is False
    )
    reasons: list[str] = []
    if not review_valid:
        reasons.append("buyer_review_snapshot_contract_failed")
    if not exchange_valid:
        reasons.append("commercial_exchange_empiredb_contract_failed")

    fresh_scout = bool(sniper["source_snapshot_fresh_under_24h"]) and (
        _fresh_timestamp(scout_snapshot.get("generated_at"), current)
    )
    fresh_review = _fresh_timestamp(buyer_review_snapshot.get("generated_at"), current)
    fresh_exchange = _fresh_timestamp(commercial_exchange_snapshot.get("observed_at"), current)
    if not fresh_scout:
        reasons.append("scanner_snapshot_stale")
    if not fresh_review:
        reasons.append("buyer_review_snapshot_stale")
    if not fresh_exchange:
        reasons.append("exchange_snapshot_stale")

    review_count = _safe_int(buyer_review_snapshot, "candidate_count")
    review_ready = _safe_int(buyer_review_snapshot, "review_ready_count")
    review_blocked = _safe_int(buyer_review_snapshot, "blocked_count")
    seats = _safe_int(commercial_exchange_snapshot, "buyer_seat_count")
    inventory = _safe_int(commercial_exchange_snapshot, "inventory_count")
    allocated = _safe_int(commercial_exchange_snapshot, "allocated_count")

    if any(value is None for value in (
        review_count, review_ready, review_blocked, seats, inventory, allocated
    )):
        reasons.append("required_counter_missing")
    elif review_ready + review_blocked != review_count:
        reasons.append("buyer_review_totals_do_not_reconcile")

    seat_counts = commercial_exchange_snapshot.get("seat_state_counts")
    if not isinstance(seat_counts, Mapping):
        reasons.append("seat_state_counts_missing")
        blocked_seats = None
        active_seats = None
    else:
        if any(type(v) is not int or v < 0 for v in seat_counts.values()):
            reasons.append("invalid_seat_state_count")
        if seats is not None and sum(
            v for v in seat_counts.values() if type(v) is int
        ) != seats:
            reasons.append("seat_count_mismatch")
        blocked_seats = seat_counts.get("blocked_missing_evidence", 0)
        active_seats = seat_counts.get("active_capacity", 0)
        if (type(blocked_seats) is not int or type(active_seats) is not int
                or blocked_seats < 0 or active_seats < 0):
            reasons.append("seat_capacity_counts_invalid")
            blocked_seats = None
            active_seats = None

    review_reasons = buyer_review_snapshot.get("blocked_reason_counts")
    if not isinstance(review_reasons, Mapping) or any(
        type(v) is not int or v < 0 for v in review_reasons.values()
    ):
        reasons.append("buyer_blocker_breakdown_invalid")
        blocker_summary: dict[str, int] = {}
    else:
        blocker_summary = {
            str(k)[:80]: v for k, v in review_reasons.items()
            if isinstance(k, str)
        }
        if review_blocked is not None and sum(blocker_summary.values()) != review_blocked:
            reasons.append("buyer_blocker_totals_do_not_reconcile")

    planning = []
    if sniper["research_rank_counts"].get("SOURCE_HOLD", 0):
        planning.append({
            "priority": 1, "owner": "source_intelligence",
            "action": "review blocked source evidence and improve allowed first-party retrieval",
            "automated_execution": False,
        })
    if blocker_summary.get("site_evidence_below_floor", 0):
        planning.append({
            "priority": 2, "owner": "buyer_acquisition_scout",
            "action": "validate first-party business sites and independent corporate identity",
            "automated_execution": False,
        })
    if blocker_summary.get("direct_buyer_evidence_missing", 0):
        planning.append({
            "priority": 3, "owner": "buyer_research",
            "action": "obtain real direct-buyer purchase or reply evidence, not intent proxies",
            "automated_execution": False,
        })
    if blocker_summary.get("official_registry_identity_mismatch", 0):
        planning.append({
            "priority": 4, "owner": "identity_review",
            "action": "resolve registry/company/website conflicts manually before any canonical link",
            "automated_execution": False,
        })
    if active_seats == 0:
        planning.append({
            "priority": 5, "owner": "buyer_capacity",
            "action": "independently verify signed terms, allowed corridor and active purchase capacity",
            "automated_execution": False,
        })
    if reasons:
        planning.insert(0, {
            "priority": 0, "owner": "production_evidence",
            "action": "refresh or repair missing/inconsistent read-only snapshot evidence",
            "automated_execution": False,
        })

    return {
        "schema_version": SCHEMA,
        "mode": "READ_ONLY_CROSS_SNAPSHOT_REVIEW",
        "state": "HOLD_EVIDENCE" if reasons else "INTERNAL_RESEARCH_READY",
        "hold_reasons": sorted(set(reasons)),
        "freshness": {
            "scout": fresh_scout, "buyer_review": fresh_review, "exchange": fresh_exchange,
        },
        "scout": {
            "research_rows": sniper["scanner_rows_observed"],
            "priority_research": sniper["research_rank_counts"].get("PRIORITY_RESEARCH", 0),
            "source_holds": sniper["research_rank_counts"].get("SOURCE_HOLD", 0),
            "regulated_holds": sniper["research_rank_counts"].get("REGULATED_HOLD", 0),
            "duplicates": sniper["duplicate_company_lane_observations"],
            "verified_buyers": 0,
        },
        "buyer_review": {
            "distinct_population_not_scout_candidates": True,
            "assessed_records": review_count,
            "review_ready_records": review_ready,
            "held_records": review_blocked,
            "blocking_reasons": dict(sorted(blocker_summary.items())),
        },
        "empiredb_exchange": {
            "independent_population_not_scanner_observations": True,
            "buyer_seat_records": seats,
            "active_capacity_seat_records": active_seats,
            "blocked_missing_evidence_seat_records": blocked_seats,
            "bounded_inventory_records": inventory,
            "allocated_records": allocated,
        },
        "priority_human_work": planning,
        "verified_buyer_delivery_available": False,
        "contact_promotion_authorized": False,
        "outreach_authorized": False,
        "review_queue_mutation_authorized": False,
        "financial_authority": False,
        "canonical_empiredb_writes": False,
        "execution_authority": "none",
        "note": "Three distinct populations; no row-level joins, cross-population totals or claims of verified commercial buyer capacity",
    }
