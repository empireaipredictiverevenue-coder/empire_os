"""Phase 4 recurring-revenue product plan for Commercial Exchange.

Modernizes historical lane-seat subscriptions without reviving legacy pricing,
SQLite commercial truth, or Solana/USDC settlement.

Launch membership pricing is founder-approved. Seat activation, fulfilment,
usage billing and revenue remain governed by verified commercial terms.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ExchangeMrrProduct:
    product_code: str
    name: str
    buyer_segment: str
    corridor_limit: int | None
    capacity_model: str
    included_features: tuple[str, ...]
    monetization: tuple[str, ...]
    lead_classes: tuple[str, ...]
    allocation_priority: str
    territory_model: str
    exclusivity_eligible: bool
    delivery_modes: tuple[str, ...]
    monthly_price_cents: int
    usage_discount_bps: int | None
    pricing_state: str = "FOUNDER_APPROVED"
    price_approved_at: str = "2026-09-24"
    binding_terms_ready: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


EXCHANGE_BASE_USAGE_PRICES_CENTS: dict[str, int] = {
    "verified": 3900,
    "qualified": 5900,
    "high_intent": 9900,
    "exclusive": 14900,
    "booked_appointment_floor": 19900,
}


EXCHANGE_MRR_PRODUCTS: tuple[ExchangeMrrProduct, ...] = (
    ExchangeMrrProduct(
        product_code="exchange_seat_starter",
        name="Commercial Exchange Starter Seat",
        buyer_segment="local_smb_and_single_market_buyers",
        corridor_limit=1,
        capacity_model="verified_buyer_capacity",
        included_features=(
            "one_corridor",
            "qualified_inventory_access",
            "capacity_dashboard",
            "overflow_visibility",
            "email_or_webhook_delivery_readiness",
        ),
        monetization=(
            "monthly_subscription",
            "usage_or_overage",
        ),
        lead_classes=("verified", "qualified"),
        allocation_priority="standard",
        territory_model="single_corridor",
        exclusivity_eligible=False,
        delivery_modes=("email", "webhook"),
        monthly_price_cents=9900,
        usage_discount_bps=0,
    ),
    ExchangeMrrProduct(
        product_code="exchange_seat_growth",
        name="Commercial Exchange Growth Seat",
        buyer_segment="growing_multi_market_buyers",
        corridor_limit=5,
        capacity_model="verified_buyer_capacity",
        included_features=(
            "five_corridors",
            "qualified_inventory_access",
            "capacity_dashboard",
            "priority_allocation_eligibility",
            "overflow_visibility",
            "webhook_delivery_readiness",
            "basic_api_access",
        ),
        monetization=(
            "monthly_subscription",
            "usage_or_overage",
            "reserved_capacity",
        ),
        lead_classes=("verified", "qualified", "high_intent"),
        allocation_priority="priority",
        territory_model="multi_corridor",
        exclusivity_eligible=False,
        delivery_modes=("email", "webhook", "api"),
        monthly_price_cents=24900,
        usage_discount_bps=1000,
    ),
    ExchangeMrrProduct(
        product_code="exchange_seat_pro",
        name="Commercial Exchange Pro Seat",
        buyer_segment="agencies_aggregators_and_multi_location_buyers",
        corridor_limit=25,
        capacity_model="verified_buyer_capacity",
        included_features=(
            "twenty_five_corridors",
            "qualified_inventory_access",
            "priority_allocation_eligibility",
            "overflow_feed",
            "api_access",
            "multi_destination_delivery",
            "capacity_forecasting",
            "buyer_performance_analytics",
        ),
        monetization=(
            "monthly_subscription",
            "usage_or_overage",
            "reserved_capacity",
            "premium_territory",
        ),
        lead_classes=(
            "verified",
            "qualified",
            "high_intent",
            "exclusive_eligible",
        ),
        allocation_priority="high_priority",
        territory_model="premium_multi_corridor",
        exclusivity_eligible=True,
        delivery_modes=("email", "webhook", "api"),
        monthly_price_cents=49900,
        usage_discount_bps=2000,
    ),
    ExchangeMrrProduct(
        product_code="exchange_seat_enterprise",
        name="Commercial Exchange Enterprise",
        buyer_segment="enterprise_networks_and_large_aggregators",
        corridor_limit=None,
        capacity_model="contract_verified_capacity",
        included_features=(
            "custom_corridors",
            "reserved_capacity",
            "private_feed",
            "api_access",
            "white_label",
            "custom_delivery",
            "dedicated_support",
            "capacity_forecasting",
            "buyer_performance_analytics",
            "governed_exclusivity_option",
        ),
        monetization=(
            "enterprise_subscription",
            "usage_or_overage",
            "reserved_capacity",
            "territory_premium",
            "exclusivity_premium",
            "private_feed",
        ),
        lead_classes=(
            "verified",
            "qualified",
            "high_intent",
            "exclusive_eligible",
            "reserved_inventory",
        ),
        allocation_priority="contract_priority",
        territory_model="custom_contract",
        exclusivity_eligible=True,
        delivery_modes=("email", "webhook", "api", "private_feed"),
        monthly_price_cents=99900,
        usage_discount_bps=None,
    ),
)


def build_exchange_mrr_product_plan() -> dict[str, Any]:
    products = [row.as_dict() for row in EXCHANGE_MRR_PRODUCTS]
    return {
        "schema_version": "empire.phase4.exchange-mrr-products.v1",
        "phase": "4",
        "status": "ACTIVE_BUILD",
        "product_count": len(products),
        "products": products,
        "upgrades_from_legacy": {
            "capacity_is_verified_not_assumed": True,
            "acquisition_continues_when_capacity_full": True,
            "overflow_remains_empire_owned": True,
            "pricing_is_founder_approved_and_governed": True,
            "territory_requires_evidence": True,
            "exclusivity_requires_explicit_terms": True,
            "delivery_requires_verified_destination": True,
            "legacy_sqlite_not_used": True,
            "legacy_usdc_solana_not_used": True,
        },
        "canonical_settlement_rail": "USDT_BSC",
        "pricing_authority": "founder_approved_2026_09_24",
        "base_usage_prices_cents": dict(EXCHANGE_BASE_USAGE_PRICES_CENTS),
        "enterprise_usage_pricing": "negotiated_or_reserved_volume",
        "binding_terms_ready": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }



def public_exchange_seat_projection() -> dict[str, Any]:
    """Public, non-binding view of Exchange seat capabilities.

    Approved launch pricing is exposed for buyer interest capture. A displayed
    price does not activate the seat or imply verified fulfilment economics.
    """
    products = []
    for row in EXCHANGE_MRR_PRODUCTS:
        products.append({
            "product_code": row.product_code,
            "name": row.name,
            "buyer_segment": row.buyer_segment,
            "corridor_limit": row.corridor_limit,
            "lead_classes": list(row.lead_classes),
            "allocation_priority": row.allocation_priority,
            "territory_model": row.territory_model,
            "exclusivity_eligible": row.exclusivity_eligible,
            "delivery_modes": list(row.delivery_modes),
            "included_features": list(row.included_features),
            "monthly_price_cents": row.monthly_price_cents,
            "monthly_price_display": f"$" + f"{row.monthly_price_cents / 100:,.0f}" + "/mo",
            "usage_discount_bps": row.usage_discount_bps,
            "pricing_state": row.pricing_state,
            "price_approved_at": row.price_approved_at,
            "binding_terms_ready": False,
        })
    return {
        "schema_version": "empire.public.exchange-seats.v1",
        "products": products,
        "count": len(products),
        "monthly_membership": True,
        "usage_or_overage": True,
        "capacity_gates_delivery_only": True,
        "overflow_remains_empire_owned": True,
        "pricing_binding": False,
        "base_usage_prices_cents": dict(EXCHANGE_BASE_USAGE_PRICES_CENTS),
        "enterprise_usage_pricing": "negotiated_or_reserved_volume",
        "actual_revenue": False,
    }
