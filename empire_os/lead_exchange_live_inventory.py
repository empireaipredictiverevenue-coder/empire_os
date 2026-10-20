"""Canonical EmpireDB Lead Exchange inventory read-model, founder-only preview.

Consumes the *existing* Commercial Exchange read-only materialization. No
database query, lead creation, task queue, buyer activation or payment call.
Scrapling/Waterfall/Sniper review packets are separate research evidence and
never increase canonical inventory or count as saleable opportunities.

"Live" here means a recent observed snapshot, NOT streaming availability.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

SCHEMA = "empire.lead_exchange_live_inventory_preview.v1"
EXCHANGE_SCHEMA = "empire.commercial_exchange_snapshot.v1"
MAX_ROWS = 1000
MAX_SEATS = 3000
MAX_PACKET_COUNT = 25
MAX_SNAPSHOT_AGE_HOURS = 6
VALID_STATES = frozenset({
    "blocked_missing_evidence", "overflow_no_capacity",
    "allocation_candidate", "allocated",
})
VALID_SEAT_STATES = frozenset({
    "blocked_missing_evidence", "active_capacity", "full",
})


def _safe_number(value: Any) -> bool:
    return type(value) is int and 0 <= value <= 1_000_000


def _time(value: Any) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def _held(reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "mode": "READ_ONLY_EXCHANGE_SNAPSHOT",
        "state": "HOLD",
        "reason": reason,
        "snapshot_fresh": False,
        "selected_inventory_records": None,
        "delivery_ready_now": 0,
        "public_inventory_claim_allowed": False,
        "public_endpoint_activated": False,
        "sellable_leads_claimed": False,
        "automated_allocation_authorized": False,
        "outbound_authorized": False,
        "payment_authorized": False,
        "canonical_empiredb_writes": False,
        "execution_authority": "none",
    }


def build_lead_exchange_live_inventory(
    exchange: Mapping[str, Any],
    *,
    sniper_packets: Sequence[Mapping[str, Any]] = (),
    now: datetime | None = None,
) -> dict[str, Any]:
    """Reconcile and aggregate ONLY canonical Exchange snapshot rows.

    Hard reject malformed snapshots; exact row counts, unique prospect IDs,
    state counts and seat states are mandatory. Never echo buyer names,
    personal contact details, prospect IDs or raw scan text into the feed.
    """
    if not isinstance(exchange, Mapping):
        return _held("canonical_exchange_missing")
    if (exchange.get("schema_version") != EXCHANGE_SCHEMA
            or exchange.get("mode") != "OBSERVE"
            or exchange.get("source") != "canonical_empiredb_projection"
            or exchange.get("canonical_backend") != "empiredb"
            or exchange.get("execution_authority") != "none"
            or exchange.get("automatic_external_delivery") is not False):
        return _held("canonical_exchange_contract_mismatch")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must have timezone")
    observed = _time(exchange.get("observed_at"))
    age = ((current - observed).total_seconds() / 3600) if observed else float("inf")
    fresh = -5 / 60 <= age <= MAX_SNAPSHOT_AGE_HOURS

    inventory = exchange.get("inventory")
    seats = exchange.get("buyer_seats")
    if (not isinstance(inventory, list) or len(inventory) > MAX_ROWS
            or not isinstance(seats, list) or len(seats) > MAX_SEATS):
        return _held("exchange_row_population_invalid")
    if (not _safe_number(exchange.get("inventory_count"))
            or exchange["inventory_count"] != len(inventory)
            or not _safe_number(exchange.get("buyer_seat_count"))
            or exchange["buyer_seat_count"] != len(seats)):
        return _held("exchange_record_count_mismatch")

    observed_states: Counter[str] = Counter()
    observed_seats: Counter[str] = Counter()
    corridor_rows: dict[tuple[str, str, str], Counter[str]] = {}
    seen_prospects = set()
    for row in inventory:
        if not isinstance(row, Mapping):
            return _held("malformed_exchange_inventory_row")
        prospect_id, state = row.get("prospect_id"), row.get("state")
        if (not isinstance(prospect_id, str) or not prospect_id.strip()
                or prospect_id in seen_prospects
                or state not in VALID_STATES):
            return _held("invalid_or_duplicate_canonical_prospect")
        seen_prospects.add(prospect_id)
        family, metro, corridor = (
            row.get("niche_family"), row.get("metro"), row.get("corridor_key")
        )
        if not all(isinstance(x, str) and 1 <= len(x) <= 120
                   for x in (family, metro, corridor)):
            # The canonical Exchange explicitly retains qualified records
            # with incomplete territory under blocked_missing_evidence. Keep
            # them in the count; never fabricate or silently discard them.
            if state != "blocked_missing_evidence":
                return _held("exchange_inventory_corridor_incomplete")
            family, metro, corridor = ("unclassified", "unverified", "unassigned")
        observed_states[state] += 1
        key = (family, metro, corridor)
        if key not in corridor_rows:
            corridor_rows[key] = Counter()
        corridor_rows[key][state] += 1

    for seat in seats:
        if not isinstance(seat, Mapping):
            return _held("malformed_exchange_buyer_seat")
        state = seat.get("seat_state")
        if state not in VALID_SEAT_STATES:
            return _held("unrecognised_buyer_seat_state")
        observed_seats[state] += 1

    def _state_counter(raw: Any, actual: Counter[str]) -> bool:
        return (
            isinstance(raw, Mapping)
            and all(
                key in actual or count == 0
                for key, count in raw.items()
            )
            and all(isinstance(key, str) and _safe_number(count)
                    for key, count in raw.items())
            and dict({key: n for key, n in raw.items() if n}) == dict(actual)
        )

    if not _state_counter(exchange.get("inventory_state_counts"), observed_states):
        return _held("inventory_state_totals_mismatch")
    if not _state_counter(exchange.get("seat_state_counts"), observed_seats):
        return _held("buyer_seat_totals_mismatch")
    for key, state in (
        ("allocation_candidate_count", "allocation_candidate"),
        ("overflow_count", "overflow_no_capacity"),
        ("blocked_missing_evidence_count", "blocked_missing_evidence"),
        ("allocated_count", "allocated"),
    ):
        if exchange.get(key) != observed_states[state] or not _safe_number(exchange.get(key)):
            return _held("allocation_state_count_mismatch")

    if (not isinstance(sniper_packets, (list, tuple))
            or len(sniper_packets) > MAX_PACKET_COUNT):
        return _held("unbounded_sniper_packet_set")
    review_only = 0
    held_packets = 0
    for packet in sniper_packets:
        if (not isinstance(packet, Mapping)
                or packet.get("schema_version") != "empire.scrapling_sniper_handoff.v1"
                or packet.get("canonical_database_writes") is not False
                or packet.get("outbound_authorized") is not False):
            return _held("untrusted_sniper_evidence")
        if packet.get("state") == "SNIPER_REVIEW_PACKET_PREPARED":
            if packet.get("live_sniper_queue_authorized") is not False:
                return _held("sniper_packet_claimed_execution")
            review_only += 1
        elif packet.get("state") == "HOLD":
            held_packets += 1
        else:
            return _held("unknown_sniper_evidence_state")

    market_rows = []
    for (niche, metro, corridor), stats in sorted(corridor_rows.items()):
        n = sum(stats.values())
        market_rows.append({
            "niche": niche,
            "metro": metro,
            "corridor": corridor,
            "selected_inventory_records": n,
            "evidence_hold_records": stats["blocked_missing_evidence"],
            "capacity_waitlist_records": stats["overflow_no_capacity"],
            "allocation_candidate_records": stats["allocation_candidate"],
            "allocated_records": stats["allocated"],
            # A snapshot is not a binding delivery/purchase commitment.
            "immediately_sellable_claim": False,
        })
    # Observations from sniper and scanner never add to this canonical number.
    # No row-level, committed allocation/delivery receipt exists in this
    # projection. Even an allocation_candidate plus an active buyer seat
    # does not by itself prove an immediately purchasable, deliverable lead.
    return {
        "schema_version": SCHEMA,
        "mode": "READ_ONLY_EXCHANGE_SNAPSHOT",
        "state": "FRESH_CANONICAL_SNAPSHOT" if fresh else "STALE_CANONICAL_SNAPSHOT",
        "observed_at": exchange.get("observed_at"),
        "snapshot_fresh": fresh,
        "snapshot_age_hours": round(age, 2) if observed else None,
        "inventory_scope": "bounded_qualified_exchange_selection_not_full_empiredb",
        "selected_inventory_records": len(inventory),
        "evidence_hold_records": observed_states["blocked_missing_evidence"],
        "buyer_capacity_waitlist_records": observed_states["overflow_no_capacity"],
        "allocation_candidate_records": observed_states["allocation_candidate"],
        "allocated_records": observed_states["allocated"],
        "delivery_ready_now": 0,
        "buyer_seat_records": len(seats),
        "active_capacity_seat_records": observed_seats["active_capacity"],
        "corridors_observed": len(market_rows),
        "markets": market_rows,
        "sniper_evidence": {
            "review_packet_count_not_inventory": review_only,
            "held_packet_count_not_inventory": held_packets,
            "included_in_canonical_inventory_count": False,
        },
        "public_inventory_claim_allowed": False,
        "public_endpoint_activated": False,
        "sellable_leads_claimed": False,
        "automated_allocation_authorized": False,
        "outbound_authorized": False,
        "payment_authorized": False,
        "canonical_empiredb_writes": False,
        "execution_authority": "none",
        "note": "Live means fresh snapshot only. Allocation candidates are not proven immediately sellable or delivered; data may change before next refresh",
    }
