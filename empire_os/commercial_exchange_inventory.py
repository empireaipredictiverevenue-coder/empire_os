"""Phase 4 Commercial Exchange read-only materialization.

Builds deterministic lane/corridor/seat/inventory projections from canonical
Supabase commercial truth. It does not create schema, allocate inventory,
send leads, accept terms, move funds or recognize revenue.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from empire_os.buyer_allocation import (
    buyer_activation_decision,
    plan_allocation,
    qualification_decision,
)
from empire_os.niche_taxonomy import metro_key, niche_family, normalise


OUTPUT = Path("runtime/commercial_exchange/latest.json")


def _safe_token(value: Any) -> str:
    text = normalise(value)
    return "".join(
        char if char.isalnum() else "_"
        for char in text
    ).strip("_")


def lane_key(family: str) -> str:
    token = _safe_token(family)
    if not token:
        raise ValueError("niche family required")
    return f"lane:v1:{token}"


def corridor_key(
    family: str,
    metro: str,
    *,
    demand_type: str = "qualified_lead",
    delivery_type: str = "lead",
) -> str:
    family_token = _safe_token(family)
    metro_token = _safe_token(metro)
    demand_token = _safe_token(demand_type)
    delivery_token = _safe_token(delivery_type)
    if not all((family_token, metro_token, demand_token, delivery_token)):
        raise ValueError("corridor identity fields required")
    return (
        f"corridor:v1:{family_token}:{metro_token}:"
        f"{demand_token}:{delivery_token}"
    )


def _remaining_capacity(row: Mapping[str, Any]) -> int:
    try:
        cap = max(int(row.get("daily_cap") or 0), 0)
    except (TypeError, ValueError):
        cap = 0
    try:
        used = max(int(row.get("calls_today") or 0), 0)
    except (TypeError, ValueError):
        used = 0
    return max(cap - used, 0)


def _delivery_type(row: Mapping[str, Any]) -> str:
    if str(row.get("webhook_url") or "").strip():
        return "webhook"
    if str(row.get("destination_phone") or "").strip():
        return "phone"
    return "unknown"


def _observed_rate(row: Mapping[str, Any]) -> float | None:
    for key in ("per_lead_rate", "base_payout"):
        raw = row.get(key)
        if raw in (None, ""):
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return None


def project_buyer_seats(
    buyers: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    seats: list[dict[str, Any]] = []
    for raw in buyers:
        row = dict(raw)
        buyer_id = str(row.get("id") or "").strip()
        if not buyer_id:
            continue

        family = niche_family(row.get("niche"))
        metro = metro_key(row.get("metro"))
        delivery = _delivery_type(row)
        activation_allowed, activation_reason = (
            buyer_activation_decision(row)
        )
        remaining = _remaining_capacity(row)

        corridor = None
        if family and metro and delivery != "unknown":
            corridor = corridor_key(
                family,
                metro,
                delivery_type=delivery,
            )

        if not activation_allowed:
            state = "blocked_missing_evidence"
        elif remaining <= 0:
            state = "full"
        else:
            state = "active_capacity"

        seats.append({
            "buyer_id": buyer_id,
            "buyer_name": str(row.get("buyer_name") or "").strip(),
            "lane_key": lane_key(family) if family else None,
            "corridor_key": corridor,
            "niche_family": family or None,
            "metro": metro or None,
            "delivery_type": delivery,
            "seat_state": state,
            "activation_reason": activation_reason,
            "remaining_capacity": remaining,
            "observed_rate": _observed_rate(row),
            "binding_price_claimed": False,
            "exclusivity_claimed": False,
            "territory_claimed_beyond_observed_metro": False,
        })

    seats.sort(
        key=lambda row: (
            str(row.get("corridor_key") or ""),
            str(row.get("buyer_id") or ""),
        )
    )
    return seats


def project_inventory(
    prospects: Iterable[Mapping[str, Any]],
    *,
    qualifications: Mapping[str, Mapping[str, Any] | None],
    identity_links: Mapping[str, Mapping[str, Any] | None],
    buyers: Iterable[Mapping[str, Any]],
    allocated_prospect_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    buyer_rows = [dict(row) for row in buyers]
    allocated = {
        str(value)
        for value in (allocated_prospect_ids or set())
        if str(value).strip()
    }
    inventory: list[dict[str, Any]] = []

    for raw in prospects:
        prospect = dict(raw)
        prospect_id = str(prospect.get("id") or "").strip()
        if not prospect_id:
            continue

        qualification = qualifications.get(prospect_id)
        allowed, qualification_reason = qualification_decision(
            dict(qualification) if isinstance(qualification, Mapping) else None
        )
        if not allowed:
            continue

        family = niche_family(prospect.get("niche"))
        metro = metro_key(prospect.get("metro"))
        if not family or not metro:
            inventory.append({
                "prospect_id": prospect_id,
                "state": "blocked_missing_evidence",
                "reason": "market_identity_missing",
                "lane_key": None,
                "corridor_key": None,
                "niche_family": family or None,
                "metro": metro or None,
                "candidate_count": 0,
                "empire_owned": True,
            })
            continue

        lane = lane_key(family)
        corridor = corridor_key(family, metro)

        if prospect_id in allocated:
            inventory.append({
                "prospect_id": prospect_id,
                "state": "allocated",
                "reason": "existing_active_fulfilment_order",
                "lane_key": lane,
                "corridor_key": corridor,
                "niche_family": family,
                "metro": metro,
                "candidate_count": 0,
                "empire_owned": False,
            })
            continue

        identity = identity_links.get(prospect_id)
        plan = plan_allocation(
            prospect,
            dict(qualification),
            dict(identity) if isinstance(identity, Mapping) else None,
            buyer_rows,
        )
        decision = str(plan.get("decision") or "")

        if decision == "ready":
            state = "allocation_candidate"
            reason = "verified_buyer_capacity_available"
            candidate_count = len(plan.get("candidates") or [])
        elif decision == "overflow_no_capacity":
            state = "overflow_no_capacity"
            reason = str(
                plan.get("reason") or "no_eligible_buyer_capacity"
            )
            candidate_count = 0
        else:
            state = "blocked_missing_evidence"
            reason = str(
                plan.get("reason") or qualification_reason
                or "missing_required_evidence"
            )
            candidate_count = 0

        inventory.append({
            "prospect_id": prospect_id,
            "state": state,
            "reason": reason,
            "lane_key": lane,
            "corridor_key": corridor,
            "niche_family": family,
            "metro": metro,
            "candidate_count": candidate_count,
            "allocation_key": plan.get("allocation_key"),
            "empire_owned": state != "allocated",
        })

    inventory.sort(
        key=lambda row: (
            str(row.get("state") or ""),
            str(row.get("corridor_key") or ""),
            str(row.get("prospect_id") or ""),
        )
    )
    return inventory


def build_exchange_snapshot(
    *,
    prospects: Iterable[Mapping[str, Any]],
    qualifications: Mapping[str, Mapping[str, Any] | None],
    identity_links: Mapping[str, Mapping[str, Any] | None],
    buyers: Iterable[Mapping[str, Any]],
    allocated_prospect_ids: set[str] | None = None,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    buyer_rows = [dict(row) for row in buyers]
    seats = project_buyer_seats(buyer_rows)
    inventory = project_inventory(
        prospects,
        qualifications=qualifications,
        identity_links=identity_links,
        buyers=buyer_rows,
        allocated_prospect_ids=allocated_prospect_ids,
    )

    inventory_counts = Counter(
        str(row.get("state") or "unknown") for row in inventory
    )
    seat_counts = Counter(
        str(row.get("seat_state") or "unknown") for row in seats
    )
    corridors = sorted({
        str(row["corridor_key"])
        for row in [*inventory, *seats]
        if row.get("corridor_key")
    })
    lanes = sorted({
        str(row["lane_key"])
        for row in [*inventory, *seats]
        if row.get("lane_key")
    })

    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("observed_at must include timezone")

    return {
        "schema_version": "empire.commercial_exchange_snapshot.v1",
        "phase": "4",
        "mode": "OBSERVE",
        "observed_at": now.astimezone(timezone.utc).isoformat(),
        "source": "canonical_supabase_projection",
        "lane_count": len(lanes),
        "corridor_count": len(corridors),
        "buyer_seat_count": len(seats),
        "inventory_count": len(inventory),
        "inventory_state_counts": dict(sorted(inventory_counts.items())),
        "seat_state_counts": dict(sorted(seat_counts.items())),
        "overflow_count": int(
            inventory_counts.get("overflow_no_capacity", 0)
        ),
        "allocation_candidate_count": int(
            inventory_counts.get("allocation_candidate", 0)
        ),
        "allocated_count": int(inventory_counts.get("allocated", 0)),
        "blocked_missing_evidence_count": int(
            inventory_counts.get("blocked_missing_evidence", 0)
        ),
        "lanes": lanes,
        "corridors": corridors,
        "buyer_seats": seats,
        "inventory": inventory,
        "buyer_capacity_gates_delivery_only": True,
        "buyer_capacity_never_gates_acquisition": True,
        "overflow_remains_empire_owned": True,
        "automatic_external_delivery": False,
        "production_schema_applied": False,
        "actual_revenue": False,
        "commercial_authority": "none",
        "payment_authority": "none",
        "revenue_recognition_authority": "none",
        "execution_authority": "none",
    }


def write_exchange_snapshot(
    repo_root: str | Path,
    payload: Mapping[str, Any],
) -> Path:
    root = Path(repo_root).resolve()
    path = root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return path
