"""Dry-run planner for canonical Revenue Exchange observations."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class MarketEvidence:
    niche: str
    metro: str
    count: int
    source: str
    evidence_refs: tuple[str, ...]
    canonical_empiredb: bool
    market_specific: bool = True


@dataclass(frozen=True)
class MarketPriceEvidence:
    niche: str
    metro: str
    amount_cents: int
    currency: str
    unit: str
    state: str
    source: str
    evidence_refs: tuple[str, ...]
    canonical_empiredb: bool


@dataclass(frozen=True)
class ObservationProposal:
    observation_key: str
    niche: str
    metro: str
    qualified_inventory_count: int
    active_buyer_capacity: int
    verified_price_per_lead_cents: tuple[int, ...]
    observed_at: str
    source: str
    evidence: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _market_key(niche: str, metro: str) -> tuple[str, str]:
    return (_clean(niche).casefold(), _clean(metro).casefold())


def _valid_market_evidence(item: MarketEvidence) -> tuple[bool, str | None]:
    if not _clean(item.niche) or not _clean(item.metro):
        return False, "market_key_missing"
    if item.count < 0:
        return False, "negative_count"
    if not item.canonical_empiredb:
        return False, "noncanonical_source"
    if not item.market_specific:
        return False, "market_specific_evidence_required"
    if not item.evidence_refs:
        return False, "evidence_refs_missing"
    source = _clean(item.source).casefold()
    if "supabase" in source or "legacy" in source or "synthetic" in source:
        return False, "rejected_source_class"
    return True, None


def _valid_price(item: MarketPriceEvidence) -> tuple[bool, str | None]:
    if not _clean(item.niche) or not _clean(item.metro):
        return False, "market_key_missing"
    if item.amount_cents <= 0:
        return False, "price_not_positive"
    if _clean(item.unit).casefold() != "per_lead":
        return False, "price_unit_not_per_lead"
    if _clean(item.state).upper() != "VERIFIED":
        return False, "price_not_verified"
    if not _clean(item.currency):
        return False, "currency_missing"
    if not item.canonical_empiredb:
        return False, "noncanonical_source"
    if not item.evidence_refs:
        return False, "evidence_refs_missing"
    source = _clean(item.source).casefold()
    if "supabase" in source or "legacy" in source or "synthetic" in source:
        return False, "rejected_source_class"
    return True, None


def plan_revenue_exchange_observations(
    *,
    inventory: Iterable[MarketEvidence],
    capacity: Iterable[MarketEvidence],
    prices: Iterable[MarketPriceEvidence],
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    now = generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("generated_at must include timezone")

    rejected: list[dict[str, Any]] = []
    inv: dict[tuple[str, str], MarketEvidence] = {}
    cap: dict[tuple[str, str], MarketEvidence] = {}
    price_map: dict[tuple[str, str], list[MarketPriceEvidence]] = {}

    for kind, rows in (("inventory", inventory), ("capacity", capacity)):
        for item in rows:
            valid, reason = _valid_market_evidence(item)
            if not valid:
                rejected.append({"kind": kind, "reason": reason, "source": item.source})
                continue
            target = inv if kind == "inventory" else cap
            target[_market_key(item.niche, item.metro)] = item

    for item in prices:
        valid, reason = _valid_price(item)
        if not valid:
            rejected.append({"kind": "price", "reason": reason, "source": item.source, "unit": item.unit})
            continue
        price_map.setdefault(_market_key(item.niche, item.metro), []).append(item)

    all_keys = sorted(set(inv) | set(cap) | set(price_map))
    candidates: list[dict[str, Any]] = []
    for key in all_keys:
        blockers: list[str] = []
        i = inv.get(key)
        c = cap.get(key)
        ps = price_map.get(key) or []
        if i is None:
            blockers.append("qualified_inventory_evidence_missing")
        if c is None:
            blockers.append("verified_market_capacity_missing")
        if not ps:
            blockers.append("verified_per_lead_price_missing")

        proposal = None
        if not blockers and i is not None and c is not None and ps:
            refs = list(i.evidence_refs) + list(c.evidence_refs)
            for p in ps:
                refs.extend(p.evidence_refs)
            refs = list(dict.fromkeys(refs))
            niche = _clean(i.niche)
            metro = _clean(i.metro)
            proposal = ObservationProposal(
                observation_key=(
                    f"revenue-exchange:{key[0]}:{key[1]}:"
                    + now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                ),
                niche=niche,
                metro=metro,
                qualified_inventory_count=i.count,
                active_buyer_capacity=c.count,
                verified_price_per_lead_cents=tuple(sorted({p.amount_cents for p in ps})),
                observed_at=now.astimezone(timezone.utc).isoformat(),
                source="canonical_empiredb_market_evidence",
                evidence={
                    "inventory_count": i.count,
                    "buyer_capacity": c.count,
                    "verified_prices_cents": sorted({p.amount_cents for p in ps}),
                    "evidence_refs": refs,
                    "currency": sorted({_clean(p.currency).upper() for p in ps}),
                },
            ).as_dict()

        candidates.append({
            "market_key": f"{key[0]}::{key[1]}",
            "proposal_ready": proposal is not None,
            "blockers": blockers,
            "proposal": proposal,
        })

    global_blockers: list[str] = []
    if not inv:
        global_blockers.append("canonical_market_inventory_unavailable")
    if not cap:
        global_blockers.append("verified_market_capacity_unavailable")
    if not price_map:
        global_blockers.append("verified_per_lead_price_unavailable")

    return {
        "schema_version": "empire.revenue_exchange.observation_plan.v1",
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "mode": "OBSERVE",
        "proposal_ready_count": sum(bool(row["proposal_ready"]) for row in candidates),
        "market_candidate_count": len(candidates),
        "global_blockers": global_blockers,
        "rejected_sources": rejected,
        "candidates": candidates,
        "execution_authority": "none",
        "database_write": False,
        "allocation_authority": "none",
        "pricing_authority": "none",
        "payment_action": False,
        "revenue_recognition": False,
    }




def _commercial_exchange_is_canonical(
    commercial_exchange: Mapping[str, Any],
) -> bool:
    return (
        _clean(commercial_exchange.get("source"))
        == "canonical_empiredb_projection"
        and _clean(commercial_exchange.get("candidate_selection"))
        == "qualification_driven"
        and _clean(commercial_exchange.get("execution_authority")) == "none"
        and commercial_exchange.get("actual_revenue") is False
    )


def project_market_evidence_from_commercial_exchange(
    commercial_exchange: Mapping[str, Any],
) -> tuple[list[MarketEvidence], list[MarketEvidence]]:
    """Aggregate canonical exchange-ready supply and active market capacity.

    Commercial Exchange observed buyer rates are intentionally ignored here;
    they are not verified Revenue Exchange price evidence.
    """
    if not _commercial_exchange_is_canonical(commercial_exchange):
        return [], []

    observed_at = _clean(commercial_exchange.get("observed_at")) or "unknown"
    snapshot_ref = f"runtime:commercial_exchange:{observed_at}"

    supply_groups: dict[tuple[str, str], dict[str, Any]] = {}
    allowed_supply_states = {"allocation_candidate", "overflow_no_capacity"}
    for raw in commercial_exchange.get("inventory") or []:
        if not isinstance(raw, Mapping):
            continue
        if _clean(raw.get("state")) not in allowed_supply_states:
            continue
        niche = _clean(raw.get("niche_family"))
        metro = _clean(raw.get("metro"))
        if not niche or not metro:
            continue
        key = _market_key(niche, metro)
        group = supply_groups.setdefault(
            key,
            {"niche": niche, "metro": metro, "count": 0, "refs": [snapshot_ref]},
        )
        group["count"] += 1
        prospect_id = _clean(raw.get("prospect_id"))
        corridor = _clean(raw.get("corridor_key"))
        if prospect_id and len(group["refs"]) < 27:
            group["refs"].append(f"prospect:{prospect_id}")
        if corridor and len(group["refs"]) < 28:
            group["refs"].append(corridor)

    inventory = [
        MarketEvidence(
            niche=group["niche"],
            metro=group["metro"],
            count=int(group["count"]),
            source="canonical_empiredb_commercial_exchange_inventory",
            evidence_refs=tuple(dict.fromkeys(group["refs"])),
            canonical_empiredb=True,
            market_specific=True,
        )
        for _, group in sorted(supply_groups.items())
    ]

    active_capacity: dict[tuple[str, str], int] = {}
    capacity_refs: dict[tuple[str, str], list[str]] = {}
    for raw in commercial_exchange.get("buyer_seats") or []:
        if not isinstance(raw, Mapping):
            continue
        if _clean(raw.get("seat_state")) != "active_capacity":
            continue
        niche = _clean(raw.get("niche_family"))
        metro = _clean(raw.get("metro"))
        if not niche or not metro:
            continue
        key = _market_key(niche, metro)
        try:
            remaining = int(raw.get("remaining_capacity") or 0)
        except (TypeError, ValueError):
            remaining = 0
        if remaining < 0:
            continue
        active_capacity[key] = active_capacity.get(key, 0) + remaining
        refs = capacity_refs.setdefault(key, [snapshot_ref])
        buyer_id = _clean(raw.get("buyer_id"))
        if buyer_id and len(refs) < 27:
            refs.append(f"buyer:{buyer_id}")

    # The buyer-seat projection is complete for this Commercial Exchange refresh.
    # Therefore every observed supply market gets an explicit active-capacity
    # observation, including zero when no activated matching seat exists.
    capacity = []
    for key, group in sorted(supply_groups.items()):
        refs = capacity_refs.get(key, [snapshot_ref])
        capacity.append(MarketEvidence(
            niche=group["niche"],
            metro=group["metro"],
            count=int(active_capacity.get(key, 0)),
            source="canonical_empiredb_commercial_exchange_buyer_capacity",
            evidence_refs=tuple(dict.fromkeys(refs)),
            canonical_empiredb=True,
            market_specific=True,
        ))

    return inventory, capacity

def plan_from_runtime_artifacts(
    *,
    commercial_exchange: Mapping[str, Any],
    buyer_capacity_readiness: Mapping[str, Any],
    commercial_catalog: Mapping[str, Any],
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    source = _clean(commercial_exchange.get("source"))
    inventory, capacity = project_market_evidence_from_commercial_exchange(
        commercial_exchange
    )

    prices: list[MarketPriceEvidence] = []
    for row in commercial_catalog.get("products") or []:
        if not isinstance(row, Mapping) or row.get("binding_terms_ready") is not True:
            continue
        pb = row.get("price_basis") or {}
        prices.append(MarketPriceEvidence(
            niche=_clean(row.get("product_family")),
            metro="",
            amount_cents=int(pb.get("amount_cents") or 0),
            currency=_clean(pb.get("currency") or row.get("currency")),
            unit=_clean(pb.get("unit")),
            state=_clean(pb.get("state")),
            source="canonical_empiredb_commercial_product_catalog",
            evidence_refs=tuple(
                _clean(ref)
                for ref in (row.get("evidence_refs") or ())
                if _clean(ref)
            ),
            canonical_empiredb=True,
        ))

    result = plan_revenue_exchange_observations(
        inventory=inventory,
        capacity=capacity,
        prices=prices,
        generated_at=generated_at,
    )
    result["runtime_source_truth"] = {
        "commercial_exchange_source": source or None,
        "commercial_exchange_canonical": _commercial_exchange_is_canonical(
            commercial_exchange
        ),
        "qualified_market_supply_count": sum(item.count for item in inventory),
        "qualified_market_count": len(inventory),
        "active_market_capacity_count": sum(item.count for item in capacity),
        "buyer_capacity_snapshot_is_market_specific": False,
        "buyer_capacity_verified_count": int(
            buyer_capacity_readiness.get("capacity_verified") or 0
        ),
        "ready_catalog_product_count": sum(
            bool(
                isinstance(row, Mapping)
                and row.get("binding_terms_ready") is True
            )
            for row in commercial_catalog.get("products") or []
        ),
        "commercial_exchange_observed_rates_promoted_to_verified_price": False,
    }
    return result
