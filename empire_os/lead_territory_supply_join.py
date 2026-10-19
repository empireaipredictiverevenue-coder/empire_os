"""Join verified unique-lead *counts* to niche+metro territory markets.

This does not allocate leads, establish rights or infer booked subscriptions.
Only accept an explicitly complete, same-snapshot canonical lead census.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from empire_os.niche_taxonomy import metro_key, niche_family


def join_verified_niche_supply(
    *,
    territory_mrr: Mapping[str, Any],
    lead_report: Mapping[str, Any],
) -> dict[str, Any]:
    if (
        lead_report.get("canonical_backend") != "empiredb"
        or lead_report.get("lead_counts_complete") is not True
        or lead_report.get("transactionally_consistent_snapshot_proven") is not True
        or (lead_report.get("snapshot_consistency") or {}).get(
            "lead_counts_same_repeatable_read_snapshot"
        ) is not True
        or territory_mrr.get("canonical_backend") != "empiredb"
    ):
        raise ValueError("complete consistent canonical lead census required")

    markets: dict[tuple[str, str], dict[str, Any]] = {}
    for market in territory_mrr.get("territory_markets", []) or []:
        niche = niche_family(market.get("niche"))
        metro = metro_key(market.get("metro"))
        if not niche or not metro:
            continue
        key = niche, metro
        if key in markets:
            raise ValueError("duplicate territory market")
        markets[key] = {
            **dict(market),
            "canonical_unique_leads_observed": 0,
            "canonical_qualified_with_evidence_observed": 0,
            "canonical_census_coverage": "observed_no_matched_supply_rows",
            "exact_delivery_match_proven": False,
            "buyer_territory_rights_verified": False,
            "sale_ready": False,
        }
    for item in lead_report.get("niche_metro_counts", []) or []:
        niche = niche_family(item.get("niche"))
        metro = metro_key(item.get("metro"))
        if not niche or not metro:
            raise ValueError("lead census contains missing niche or metro")
        count = item.get("unique_leads_observed")
        qualified = item.get("qualified_with_evidence_observed")
        if type(count) is not int or type(qualified) is not int:
            raise ValueError("noninteger canonical market counts")
        if count < 0 or qualified < 0 or qualified > count:
            raise ValueError("impossible canonical market counts")
        key = (niche, metro)
        market = markets.setdefault(key, {
            "niche": niche,
            "metro": metro,
            "distinct_corridor_keys": 0,
            "buyer_seat_records": 0,
            "verified_active_capacity_records": 0,
            "sampled_qualified_inventory_records": 0,
            "sampled_overflow_records": 0,
            "exact_route_compatibility_verified": False,
            "territory_rights_verified": False,
            "exclusive_territory_reserved": False,
            "sale_ready": False,
            "readiness": "NO_VERIFIED_BUYER_CAPACITY",
            "canonical_unique_leads_observed": 0,
            "canonical_qualified_with_evidence_observed": 0,
            "canonical_census_coverage": "observed_no_matched_supply_rows",
            "exact_delivery_match_proven": False,
            "buyer_territory_rights_verified": False,
        })
        if market["canonical_census_coverage"] == "canonical_supply_recorded":
            raise ValueError("duplicate niche/metro lead census entry")
        market["canonical_unique_leads_observed"] = count
        market["canonical_qualified_with_evidence_observed"] = qualified
        market["canonical_census_coverage"] = "canonical_supply_recorded"

    total_unique = sum(
        r["canonical_unique_leads_observed"] for r in markets.values()
    )
    total_qualified = sum(
        r["canonical_qualified_with_evidence_observed"] for r in markets.values()
    )
    if (
        total_unique != lead_report.get("unique_prospects_observed")
        or total_qualified != lead_report.get("qualified_with_evidence_observed")
    ):
        raise ValueError("territory join does not reconcile complete census totals")

    ordered = sorted(
        markets.values(),
        key=lambda m: (
            -m["canonical_qualified_with_evidence_observed"],
            -m["canonical_unique_leads_observed"],
            m["niche"], m["metro"],
        ),
    )
    states = Counter()
    for item in ordered:
        if item["verified_active_capacity_records"] == 0:
            item["next_action"] = "verify_real_buyer_and_delivery_capacity"
            states["needs_verified_buyer_capacity"] += 1
        elif item["canonical_qualified_with_evidence_observed"] == 0:
            item["next_action"] = "qualify_owned_supply_and_evidence"
            states["needs_qualified_supply"] += 1
        else:
            item["next_action"] = "verify_delivery_route_territory_terms_and_price"
            states["review_commercial_gate"] += 1
        if item["distinct_corridor_keys"] == 0:
            item["canonical_supply_market_without_exchange_corridor"] = True
            states["markets_not_yet_in_exchange"] += 1
        else:
            item["canonical_supply_market_without_exchange_corridor"] = False

    return {
        **dict(territory_mrr),
        "territory_markets": ordered,
        "territory_market_count": len(ordered),
        "complete_canonical_niche_supply_join_available": True,
        "canonical_unique_prospects_reconciled": total_unique,
        "canonical_qualified_with_evidence_reconciled": total_qualified,
        "canonical_census_observed_at": lead_report["observed_at"],
        "markets_without_exchange_corridor_count": states[
            "markets_not_yet_in_exchange"
        ],
        "market_next_action_counts": dict(sorted(states.items())),
        "scoring_and_supply_are_not_verified_deliverable_inventory": True,
        "buyer_entitlement_or_exclusivity_inferred": False,
        "revenue_or_subscription_activation_authorized": False,
        "execution_authority": "none",
    }
