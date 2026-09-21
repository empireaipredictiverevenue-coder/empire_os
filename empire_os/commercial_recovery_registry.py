"""Read-only commercial recovery registry.

This registry preserves product/revenue opportunities recovered from historical
Empire blueprints without promoting them into the governed sellable catalog.

It has no pricing, payment, terms, fulfilment or execution authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


VALID_STATES = {
    "PRODUCTION",
    "ACTIVE_BUILD",
    "INCUBATE",
    "SALVAGE_CANDIDATE",
    "REBUILD_LATER",
    "REFERENCE_ONLY",
    "RETIRED",
    "FOUNDER_GATE",
}


@dataclass(frozen=True)
class RecoveryProduct:
    key: str
    name: str
    state: str
    family: str
    revenue_models: tuple[str, ...]
    surfaces: tuple[str, ...]
    notes: str = ""
    pricing_observed: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


RECOVERY_PRODUCTS: tuple[RecoveryProduct, ...] = (
    RecoveryProduct(
        key="permit_intelligence",
        name="Permit Intelligence",
        state="ACTIVE_BUILD",
        family="public_record_intelligence",
        revenue_models=("subscription", "data_api", "managed_service", "white_label"),
        surfaces=("permit_radar", "alerts", "territory_feed", "buyer_feed", "api"),
    ),
    RecoveryProduct(
        key="property_intelligence",
        name="Property Intelligence",
        state="ACTIVE_BUILD",
        family="property",
        revenue_models=("subscription", "data_api", "enterprise", "managed_service"),
        surfaces=("property_radar", "portfolio_monitor", "opportunity_feed", "api"),
    ),
    RecoveryProduct(
        key="private_capital_rollup",
        name="Private Capital & Roll-Up Intelligence",
        state="ACTIVE_BUILD",
        family="private_capital",
        revenue_models=("enterprise", "data_api", "managed_service", "white_label"),
        surfaces=("sponsor_intelligence", "portfolio_intelligence", "addon_radar", "market_map"),
    ),
    RecoveryProduct(
        key="oil_gas_intelligence",
        name="Oil & Gas / Energy Infrastructure Intelligence",
        state="INCUBATE",
        family="energy_infrastructure",
        revenue_models=("subscription", "data_api", "enterprise", "managed_service"),
        surfaces=("operator_asset_radar", "permit_activity_feed", "infrastructure_map", "trigger_alerts"),
        notes="Research/source/legal/buyer validation required before promotion.",
    ),
    RecoveryProduct(
        key="storm_weather_intelligence",
        name="Storm & Weather Intelligence",
        state="ACTIVE_BUILD",
        family="physical_intelligence",
        revenue_models=("transactional", "subscription", "data_api", "managed_service"),
        surfaces=("storm_leads_multiplier", "territory_alerts", "opportunity_feed", "api"),
    ),
    RecoveryProduct(
        key="satellite_volumetric_intelligence",
        name="Satellite / Volumetric Intelligence",
        state="ACTIVE_BUILD",
        family="spatial_intelligence",
        revenue_models=("subscription", "data_api", "enterprise"),
        surfaces=("imagery_evidence", "post_event_compare", "asset_monitoring"),
    ),
    RecoveryProduct(
        key="warehouse_industrial_radar",
        name="Warehouse / Industrial / Idle-Asset Radar",
        state="INCUBATE",
        family="industrial_intelligence",
        revenue_models=("subscription", "data_api", "enterprise"),
        surfaces=("industrial_radar", "capacity_signals", "corridor_feed"),
    ),
    RecoveryProduct(
        key="market_revenue_gps",
        name="Market Intelligence / Revenue GPS",
        state="ACTIVE_BUILD",
        family="market_intelligence",
        revenue_models=("subscription", "data_api", "enterprise", "managed_service"),
        surfaces=("market_maps", "tam", "opportunity_feed", "revenue_gps"),
    ),
    RecoveryProduct(
        key="revenue_pulse",
        name="Revenue Pulse",
        state="ACTIVE_BUILD",
        family="revenue_intelligence",
        revenue_models=("subscription", "enterprise", "managed_service"),
        surfaces=("command_tower", "node_pulse", "revenue_blocker", "forecast_actual"),
    ),
    RecoveryProduct(
        key="search_intelligence_suite",
        name="Search / SEO / AEO / GEO Intelligence",
        state="ACTIVE_BUILD",
        family="search_intelligence",
        revenue_models=("subscription", "usage", "data_api", "managed_service", "white_label"),
        surfaces=("audit", "serp_api", "opportunity_map", "search_growth_command"),
    ),
    RecoveryProduct(
        key="revenue_leak_audit",
        name="Revenue Leak / Commercial Audit",
        state="SALVAGE_CANDIDATE",
        family="commercial_diagnostics",
        revenue_models=("transactional", "lead_magnet", "managed_service"),
        surfaces=("scanner", "audit", "roi_diagnostic"),
    ),
    RecoveryProduct(
        key="intel_hourly",
        name="Hourly Intelligence Retainer",
        state="FOUNDER_GATE",
        family="high_touch_intelligence",
        revenue_models=("hourly", "retainer", "managed_service"),
        surfaces=("intelligence_block", "market_review", "opportunity_review"),
        notes="Historical $150/hour exists only as legacy evidence; current pricing is unapproved.",
    ),
    RecoveryProduct(
        key="omega_evaluation",
        name="Omega Evaluation / Value Meter",
        state="SALVAGE_CANDIDATE",
        family="scoring_intelligence",
        revenue_models=("usage", "credit_pack", "performance"),
        surfaces=("evaluation", "grading", "value_meter"),
    ),
    RecoveryProduct(
        key="opportunity_marketplace",
        name="Lead / Opportunity Marketplace",
        state="REBUILD_LATER",
        family="marketplace",
        revenue_models=("transactional", "usage", "performance"),
        surfaces=("buyer_waterfall", "allocation", "marketplace"),
    ),
    RecoveryProduct(
        key="managed_growth",
        name="Managed Growth / Done-For-You",
        state="ACTIVE_BUILD",
        family="managed_execution",
        revenue_models=("project", "retainer", "subscription", "performance"),
        surfaces=("seo_aeo_geo", "campaigns", "content", "demand_generation"),
    ),
    RecoveryProduct(
        key="enterprise_white_label",
        name="Enterprise / White Label / Partner",
        state="ACTIVE_BUILD",
        family="channel_enterprise",
        revenue_models=("enterprise", "license", "reseller", "data_api"),
        surfaces=("enterprise_workspace", "white_label", "partner_api", "reseller"),
    ),
)


def recovery_product_catalog() -> list[dict[str, Any]]:
    """Return immutable recovery metadata as plain dictionaries."""
    return [product.as_dict() for product in RECOVERY_PRODUCTS]


def recovery_summary() -> dict[str, Any]:
    by_state: dict[str, int] = {}
    by_family: dict[str, int] = {}
    for product in RECOVERY_PRODUCTS:
        by_state[product.state] = by_state.get(product.state, 0) + 1
        by_family[product.family] = by_family.get(product.family, 0) + 1
    return {
        "schema_version": "empire.commercial-recovery.v1",
        "product_count": len(RECOVERY_PRODUCTS),
        "by_state": dict(sorted(by_state.items())),
        "by_family": dict(sorted(by_family.items())),
        "pricing_observed_count": sum(
            product.pricing_observed is True for product in RECOVERY_PRODUCTS
        ),
        "execution_authority": "none",
        "actual_revenue": False,
    }
