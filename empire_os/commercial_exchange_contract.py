"""Canonical Phase 4 Commercial Exchange contract.

This module defines the execution contract for Phase 4 without creating schema
or granting commercial authority. It separates canonical Supabase-native
commercial truth from legacy SQLite lane/seat concepts that may be salvaged
only as design reference.

Core invariant:
Buyer capacity gates delivery/allocation only. It never gates acquisition.
Qualified inventory that cannot be allocated remains Empire-owned overflow.
"""
from __future__ import annotations

from typing import Any


CANONICAL_SOURCE_TABLES = (
    "prospects",
    "prospect_qualifications",
    "prospect_entity_links",
    "gtm_opportunities",
    "buyers",
    "buyer_commercial_evidence",
    "buyer_capacity_intakes",
    "buyer_subscriptions",
    "fulfilment_orders",
)

LEGACY_REFERENCE_ONLY = (
    "empire_os/lanes.py",
    "empire_os/seat_corridors.py",
    "lane_leads",
    "strike_pack_lanes",
    "buyer_leads",
)

REQUIRED_EXCHANGE_OBJECTS = (
    "exchange_lanes",
    "exchange_corridors",
    "buyer_seats",
    "qualified_inventory",
    "overflow_inventory",
)

AUTOMATED_INTERNAL_LOOPS = (
    "qualified_inventory_refresh",
    "buyer_capacity_refresh",
    "seat_readiness_refresh",
    "corridor_readiness_refresh",
    "allocation_proposal_refresh",
    "overflow_inventory_refresh",
)


def build_commercial_exchange_contract() -> dict[str, Any]:
    return {
        "schema_version": "empire.commercial_exchange_contract.v1",
        "phase": "4",
        "phase_title": "Commercial Exchange",
        "status": "CURRENT",
        "mode": "OBSERVE",
        "objective": (
            "Turn qualified opportunities into governed Empire-owned "
            "inventory and deterministic buyer-allocation proposals."
        ),
        "canonical_source_tables": list(CANONICAL_SOURCE_TABLES),
        "legacy_reference_only": list(LEGACY_REFERENCE_ONLY),
        "required_exchange_objects": list(REQUIRED_EXCHANGE_OBJECTS),
        "entity_model": {
            "lane": (
                "Commercial grouping for compatible corridors; it does not "
                "own buyer capacity or imply exclusivity."
            ),
            "corridor": (
                "Niche/product × territory × demand type × delivery type."
            ),
            "buyer_seat": (
                "A buyer's governed commercial right and verified capacity "
                "within one corridor."
            ),
            "qualified_inventory": (
                "Empire-owned opportunity inventory that passed qualification "
                "and identity/evidence gates."
            ),
            "overflow_inventory": (
                "Qualified Empire-owned inventory not currently deliverable "
                "because no eligible verified buyer capacity is available."
            ),
        },
        "invariants": {
            "buyer_capacity_gates_delivery_only": True,
            "buyer_capacity_never_gates_acquisition": True,
            "overflow_remains_empire_owned": True,
            "full_seats_do_not_stop_acquisition": True,
            "pricing_requires_verified_evidence": True,
            "historical_pricing_is_not_current_pricing": True,
            "seat_activation_requires_verified_terms": True,
            "seat_activation_requires_verified_capacity": True,
            "territory_requires_evidence": True,
            "exclusivity_requires_evidence": True,
            "allocation_must_be_deterministic_and_auditable": True,
            "no_synthetic_inventory": True,
            "unknown_stays_unknown": True,
        },
        "allocation_states": (
            "qualified_inventory",
            "allocation_candidate",
            "allocated",
            "overflow_no_capacity",
            "blocked_missing_evidence",
        ),
        "overflow_routes": (
            "alternate_corridor",
            "alternate_buyer",
            "marketplace_or_feed",
            "nurture",
            "future_capacity",
        ),
        "automation": {
            "internal_loops": list(AUTOMATED_INTERNAL_LOOPS),
            "automatic_acquisition_continues_when_capacity_full": True,
            "automatic_external_delivery": False,
            "automatic_commercial_terms_acceptance": False,
            "automatic_fund_movement": False,
            "automatic_revenue_recognition": False,
        },
        "revenue_features": (
            "buyer_seat_subscriptions",
            "corridor_subscriptions",
            "dynamic_buyer_pricing",
            "capacity_usage_economics",
            "overflow_monetisation",
            "margin_aware_routing",
            "demand_pre_selling",
            "reserved_future_capacity",
            "territory_and_exclusivity_premiums",
        ),
        "production_schema_applied": False,
        "external_execution_performed": False,
        "actual_revenue": False,
        "commercial_authority": "none",
        "payment_authority": "none",
        "revenue_recognition_authority": "none",
        "execution_authority": "none",
    }
