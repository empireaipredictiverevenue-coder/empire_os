"""Private, non-binding Exchange seats/MRR/territory evidence projection.

Source of product terms: active founder-approved Phase 4 catalogue.
Source of lead/capacity readiness: canonical EmpireDB exchange snapshot.
Optional legacy pack/subscription inventory is visible as unverified records,
never as contracted rights, fulfilled seats, payments or realised MRR.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from empire_os.niche_taxonomy import niche_family, normalise
from empire_os.phase4_exchange_mrr_products import (
    EXCHANGE_MRR_PRODUCTS,
    EXCHANGE_BASE_USAGE_PRICES_CENTS,
)


def _niche(value: Any) -> str:
    return niche_family(value) or "unclassified"


def _is_current(subscription: Mapping[str, Any], at: datetime) -> bool:
    if subscription.get("active") is not True:
        return False
    if str(subscription.get("status") or "").lower() != "active":
        return False
    for name, lower_bound in (("period_start", True), ("period_end", False)):
        value = subscription.get(name)
        if value in (None, ""):
            continue
        try:
            when = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if when.tzinfo is None:
                return False
        except (ValueError, TypeError):
            return False
        if lower_bound and when > at:
            return False
        if not lower_bound and when <= at:
            return False
    return True


def build_territory_mrr_bridge(
    *,
    exchange: Mapping[str, Any],
    strike_packs: Iterable[Mapping[str, Any]] | None = None,
    buyer_subscriptions: Iterable[Mapping[str, Any]] | None = None,
    observed_at: datetime | None = None,
    subscriptions_reader_available: bool = False,
    strike_packs_reader_available: bool = False,
) -> dict[str, Any]:
    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("observed_at must be timezone-aware")
    if exchange.get("canonical_backend") != "empiredb":
        raise ValueError("canonical EmpireDB exchange snapshot required")
    seats = list(exchange.get("buyer_seats") or [])
    inventory = list(exchange.get("inventory") or [])
    by_buyer = {
        str(row.get("buyer_id")): row
        for row in seats if row.get("buyer_id")
    }

    raw_packs = list(strike_packs or [])
    packs = []
    for row in raw_packs:
        niches = row.get("niches")
        if not isinstance(niches, (list, tuple)):
            niches = []
        packs.append({
            "pack_id": str(row.get("id") or ""),
            "code": str(row.get("slug") or ""),
            "name": str(row.get("name") or ""),
            "tier": str(row.get("tier") or ""),
            "niche_families": sorted({_niche(n) for n in niches if str(n).strip()}),
            "declared_lane_count": row.get("lane_count"),
            "monthly_price_cents": row.get("monthly_price_cents"),
            "price_per_lead_cents": row.get("price_per_lead_cents"),
            "max_leads_per_month": row.get("max_leads_per_month"),
            "catalog_active": row.get("is_active") is True,
            "catalog_public": row.get("is_public") is True,
            "seat_entitlement_verified": False,
            "current_mrr_verified": False,
            "legacy_compatibility_record": True,
        })
    packs.sort(key=lambda r: (r["tier"], r["code"]))
    by_pack_id = {
        row["pack_id"]: row for row in packs if row["pack_id"]
    }

    states: Counter[str] = Counter()
    claimed_current_subscriptions = 0
    unknown_buyer_linkage = 0
    unverified_catalog_subscriptions = 0
    gross_nominal_monthly_cents = 0
    matched_active_capacity_subscription_records = 0
    by_niche: dict[str, Counter[str]] = defaultdict(Counter)
    by_corridor: dict[str, Counter[str]] = defaultdict(Counter)
    for row in buyer_subscriptions or ():
        states[str(row.get("status") or "unknown").lower()] += 1
        buyer_id = str(row.get("buyer_id") or "")
        seat = by_buyer.get(buyer_id)
        pack = by_pack_id.get(str(row.get("pack_id") or ""))
        if not seat:
            unknown_buyer_linkage += 1
        if not pack:
            unverified_catalog_subscriptions += 1
        if not _is_current(row, now):
            continue
        claimed_current_subscriptions += 1
        try:
            amount = int(row.get("monthly_price_cents"))
        except (TypeError, ValueError):
            amount = 0
        if amount > 0:
            gross_nominal_monthly_cents += amount
        if not seat:
            continue
        niche = _niche(seat.get("niche_family"))
        by_niche[niche]["marked_active_subscription_rows"] += 1
        if seat.get("seat_state") == "active_capacity":
            matched_active_capacity_subscription_records += 1
            by_niche[niche]["matching_verified_capacity_seat_records"] += 1
        else:
            by_niche[niche]["blocked_buyer_seat_records"] += 1
        corridor = str(seat.get("corridor_key") or "")
        if corridor:
            by_corridor[corridor]["marked_active_subscription_rows"] += 1

    corridor_data = {}
    for row in seats:
        key = str(row.get("corridor_key") or "")
        if not key:
            continue
        item = corridor_data.setdefault(key, {
            "corridor_key": key,
            "niche": _niche(row.get("niche_family")),
            "metro": normalise(row.get("metro")) or "unclassified",
            "buyer_seat_records": 0,
            "verified_active_capacity_records": 0,
            "sampled_qualified_inventory_records": 0,
            "sampled_overflow_records": 0,
        })
        item["buyer_seat_records"] += 1
        if row.get("seat_state") == "active_capacity":
            item["verified_active_capacity_records"] += 1

    for row in inventory:
        key = str(row.get("corridor_key") or "")
        if not key:
            continue
        item = corridor_data.setdefault(key, {
            "corridor_key": key,
            "niche": _niche(row.get("niche_family")),
            "metro": normalise(row.get("metro")) or "unclassified",
            "buyer_seat_records": 0,
            "verified_active_capacity_records": 0,
            "sampled_qualified_inventory_records": 0,
            "sampled_overflow_records": 0,
        })
        item["sampled_qualified_inventory_records"] += 1
        if row.get("state") == "overflow_no_capacity":
            item["sampled_overflow_records"] += 1

    territories = []
    for key, record in sorted(corridor_data.items()):
        record = dict(record)
        record["subscription_rows_marked_active"] = (
            by_corridor[key]["marked_active_subscription_rows"]
            if subscriptions_reader_available else None
        )
        record["lead_supply_view_is_qualified_sample_only"] = True
        record["buyer_territory_rights_verified"] = False
        record["exclusivity_granted"] = False
        record["ready_for_binding_sale"] = False
        territories.append(record)

    # Group commercially meaningful markets by niche+metro. Supply uses
    # delivery_type=lead while a buyer seat uses webhook/phone: the exact
    # corridor keys differ intentionally and MUST NOT be equated.
    markets_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for territory in territories:
        market_key = (territory["niche"], territory["metro"])
        market = markets_by_key.setdefault(market_key, {
            "niche": territory["niche"],
            "metro": territory["metro"],
            "distinct_corridor_keys": 0,
            "buyer_seat_records": 0,
            "verified_active_capacity_records": 0,
            "sampled_qualified_inventory_records": 0,
            "sampled_overflow_records": 0,
            "exact_route_compatibility_verified": False,
            "territory_rights_verified": False,
            "exclusive_territory_reserved": False,
            "sale_ready": False,
        })
        market["distinct_corridor_keys"] += 1
        for field in (
            "buyer_seat_records",
            "verified_active_capacity_records",
            "sampled_qualified_inventory_records",
            "sampled_overflow_records",
        ):
            market[field] += territory[field]
    markets = []
    for key, market in sorted(markets_by_key.items()):
        market = dict(market)
        if market["verified_active_capacity_records"] == 0:
            market["readiness"] = "NO_VERIFIED_BUYER_CAPACITY"
        elif market["sampled_qualified_inventory_records"] == 0:
            market["readiness"] = "CAPACITY_WITHOUT_SAMPLED_SUPPLY"
        else:
            market["readiness"] = "REVIEW_DELIVERY_ROUTE_AND_TERMS"
        markets.append(market)

    offer_catalog = [{
        "code": item.product_code,
        "name": item.name,
        "monthly_price_cents": item.monthly_price_cents,
        "currency": "USD",
        "corridor_limit": item.corridor_limit,
        "territory_model": item.territory_model,
        "lead_classes": list(item.lead_classes),
        "delivery_modes": list(item.delivery_modes),
        "exclusivity_eligible": item.exclusivity_eligible,
        "usage_discount_bps": item.usage_discount_bps,
        "pricing_state": item.pricing_state,
        "binding_terms_ready": item.binding_terms_ready,
        "verified_subscription_count": None,
        "reserved_territory_count": None,
    } for item in EXCHANGE_MRR_PRODUCTS]

    return {
        "schema_version": "empire.territory_mrr_lead_bridge.v1",
        "mode": "OBSERVE",
        "observed_at": now.astimezone(timezone.utc).isoformat(),
        "exchange_observed_at": exchange.get("observed_at"),
        "canonical_backend": "empiredb",
        "product_catalog": offer_catalog,
        "product_catalog_count": len(offer_catalog),
        "base_usage_prices_cents": dict(EXCHANGE_BASE_USAGE_PRICES_CENTS),
        "catalog_price_is_binding": False,
        "catalog_price_is_recognized_mrr": False,
        "territories": territories,
        "territory_count": len(territories),
        "territory_markets": markets,
        "territory_market_count": len(markets),
        "territory_market_grain": "niche_family_plus_metro_not_route_entitlement",
        "raw_buyer_and_supply_corridor_keys_not_equivalent": True,
        "strike_packs_reader_available": strike_packs_reader_available,
        "strike_pack_record_count": len(packs) if strike_packs_reader_available else None,
        "strike_packs": packs if strike_packs_reader_available else [],
        "buyer_subscriptions_reader_available": subscriptions_reader_available,
        "buyer_subscription_record_count": (
            sum(states.values()) if subscriptions_reader_available else None
        ),
        "buyer_subscription_status_counts": (
            dict(sorted(states.items())) if subscriptions_reader_available else {}
        ),
        "marked_active_subscription_record_count": (
            claimed_current_subscriptions if subscriptions_reader_available else None
        ),
        "nominal_monthly_contract_field_cents_unverified": (
            gross_nominal_monthly_cents if subscriptions_reader_available else None
        ),
        "subscription_rows_with_no_buyer_seat_match": (
            unknown_buyer_linkage if subscriptions_reader_available else None
        ),
        "subscription_rows_with_no_pack_match": (
            unverified_catalog_subscriptions
            if (subscriptions_reader_available and strike_packs_reader_available)
            else None
        ),
        "subscription_rows_matching_active_capacity": (
            matched_active_capacity_subscription_records
            if subscriptions_reader_available else None
        ),
        "by_niche": [
            {"niche": key, **dict(sorted(value.items()))}
            for key, value in sorted(by_niche.items())
        ] if subscriptions_reader_available else [],
        "source_of_recognized_mrr": "not_proven_by_subscription_rows",
        "actual_mrr_cents": None,
        "payment_verified": False,
        "signed_contract_verified": False,
        "territory_exclusivity_verified": False,
        "subscription_entitlement_verified": False,
        "tenant_self_serve_seat_activation_authorized": False,
        "lead_delivery_authorized": False,
        "no_legacy_stripe_inference": True,
        "no_legacy_sqlite_inference": True,
        "execution_authority": "none",
    }
