"""Machine-readable recovery map for historical EmpireOS MRR products.

This module does not make legacy prices current. It classifies historical
subscription/SKU products for migration into the governed commercial catalog.

Legacy SQLite, USDC/Solana settlement and historical prices are evidence only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


VALID_DISPOSITIONS = {
    "MIGRATE",
    "MERGE",
    "REBUILD",
    "INCUBATE",
    "REFERENCE_ONLY",
    "RETIRE",
}


@dataclass(frozen=True)
class MrrRecoveryProduct:
    key: str
    historical_name: str
    source_path: str
    disposition: str
    target_family: str
    target_phase: str
    revenue_models: tuple[str, ...]
    current_mapping: tuple[str, ...]
    notes: str
    legacy_pricing_present: bool = False
    legacy_pricing_approved_current: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


MRR_RECOVERY_PRODUCTS: tuple[MrrRecoveryProduct, ...] = (
    MrrRecoveryProduct(
        key="platform_saas_tiers",
        historical_name=(
            "EmpireOS SaaS Plans: Starter / Team / Enterprise / "
            "Scale / Whale / Sovereign"
        ),
        source_path="empire_os/tenants.py",
        disposition="REBUILD",
        target_family="saas_platform",
        target_phase="8",
        revenue_models=("subscription", "seat", "usage", "enterprise"),
        current_mapping=(
            "saas_usage_billing",
            "enterprise_white_label",
            "commercial_product_catalog",
        ),
        notes=(
            "Core plan/seat/quota architecture is reusable. Historical "
            "SQLite subscription state and pricing are not canonical. "
            "Rebuild on Supabase entitlements, verified terms, usage meter, "
            "USDT/BSC settlement and Revenue Truth."
        ),
        legacy_pricing_present=True,
    ),
    MrrRecoveryProduct(
        key="lane_seat_subscription_tiers",
        historical_name=(
            "Buyer Lane Seats: Bronze / Silver / Gold / Diamond / "
            "Empire / Titanium"
        ),
        source_path="empire_os/marketplace.py",
        disposition="MIGRATE",
        target_family="commercial_exchange",
        target_phase="4",
        revenue_models=(
            "subscription",
            "seat",
            "usage",
            "transactional",
            "performance",
            "enterprise",
        ),
        current_mapping=(
            "lane_seat_corridor_exchange",
            "buyer_seats",
            "exchange_corridors",
            "overflow_inventory",
        ),
        notes=(
            "Strong Phase 4 concept. Migrate seat/capacity/overage ideas only. "
            "Old SQLite marketplace, direct delivery and historical pricing "
            "must not be promoted as current commercial truth."
        ),
        legacy_pricing_present=True,
    ),
    MrrRecoveryProduct(
        key="empire_leads_engine",
        historical_name="Empire Leads Engine",
        source_path="empire_os/seed_sku_products.py",
        disposition="MERGE",
        target_family="commercial_exchange",
        target_phase="4",
        revenue_models=("subscription", "usage", "managed_service"),
        current_mapping=(
            "lane_seat_corridor_exchange",
            "managed_growth",
            "buyer_acquisition_team",
        ),
        notes=(
            "Merge into current acquisition + Commercial Exchange rather than "
            "reviving as a separate SQLite SKU."
        ),
        legacy_pricing_present=True,
    ),
    MrrRecoveryProduct(
        key="hermes_framework",
        historical_name="Hermes Framework",
        source_path="empire_os/seed_sku_products.py",
        disposition="REBUILD",
        target_family="agent_platform",
        target_phase="10",
        revenue_models=("subscription", "enterprise", "private_agent"),
        current_mapping=("empire_coder", "advanced_autonomy"),
        notes=(
            "Recover as governed private-agent/agent-runtime product, not the "
            "old packaged SKU."
        ),
        legacy_pricing_present=True,
    ),
    MrrRecoveryProduct(
        key="opencut_studio",
        historical_name="OpenCut Studio",
        source_path="empire_os/seed_sku_products.py",
        disposition="INCUBATE",
        target_family="creative_automation",
        target_phase="8",
        revenue_models=("subscription", "usage", "managed_service"),
        current_mapping=("ads_media_buyer", "content_automation"),
        notes=(
            "Useful only if current creative/video automation is verified as "
            "a coherent sellable surface. Do not revive the old SKU blindly."
        ),
        legacy_pricing_present=True,
    ),
    MrrRecoveryProduct(
        key="empire_templates",
        historical_name="Empire Templates",
        source_path="empire_os/seed_sku_products.py",
        disposition="MERGE",
        target_family="growth_enablement",
        target_phase="8",
        revenue_models=("subscription", "bundle", "white_label"),
        current_mapping=("managed_growth", "white_label"),
        notes=(
            "Templates are better packaged inside SaaS/managed-growth tiers "
            "than sold as a standalone legacy SKU."
        ),
        legacy_pricing_present=True,
    ),
    MrrRecoveryProduct(
        key="marketingskills",
        historical_name="MarketingSkills",
        source_path="empire_os/seed_sku_products.py",
        disposition="MERGE",
        target_family="growth_enablement",
        target_phase="8",
        revenue_models=("subscription", "bundle"),
        current_mapping=("managed_growth", "autonomous_gtm"),
        notes=(
            "Recover capabilities into GTM/managed-growth product tiers; avoid "
            "duplicating internal skill assets as a separate product unless "
            "there is customer-facing value."
        ),
        legacy_pricing_present=True,
    ),
    MrrRecoveryProduct(
        key="satellite_idle_watch",
        historical_name="Satellite Idle Watch",
        source_path="empire_os/seed_sku_products.py",
        disposition="MERGE",
        target_family="industrial_intelligence",
        target_phase="6",
        revenue_models=("subscription", "alerts", "data_api"),
        current_mapping=(
            "warehouse_industrial_radar",
            "satellite_volumetric_intelligence",
        ),
        notes=(
            "Merge into industrial/physical-intelligence subscriptions and "
            "alerts. Existing old SKU price is not current evidence."
        ),
        legacy_pricing_present=True,
    ),
    MrrRecoveryProduct(
        key="skillspector_audit",
        historical_name="SkillSpector Audit",
        source_path="empire_os/seed_sku_products.py",
        disposition="INCUBATE",
        target_family="commercial_diagnostics",
        target_phase="8",
        revenue_models=("transactional", "audit", "subscription"),
        current_mapping=("revenue_leak_audit", "commercial_diagnostics"),
        notes=(
            "Keep only if the current diagnostics engine can produce a "
            "customer-relevant audit with verified evidence."
        ),
        legacy_pricing_present=True,
    ),
    MrrRecoveryProduct(
        key="synthetic_agent",
        historical_name="Synthetic Agent",
        source_path="empire_os/seed_sku_products.py",
        disposition="RETIRE",
        target_family="agent_platform",
        target_phase="10",
        revenue_models=("subscription",),
        current_mapping=(),
        notes=(
            "Retire the legacy SKU name/implementation because synthetic/mock "
            "production behaviour conflicts with current truth rules. Any "
            "future agent product must be rebuilt from governed real-data "
            "runtime components."
        ),
        legacy_pricing_present=True,
    ),
    MrrRecoveryProduct(
        key="aeo_monitor",
        historical_name="AEO Monitor",
        source_path="empire_os/seed_sku_products.py",
        disposition="MERGE",
        target_family="search_intelligence",
        target_phase="8",
        revenue_models=("subscription", "alerts"),
        current_mapping=("geo_ai_visibility", "search_growth_command"),
        notes=(
            "Already superseded by the now-governed AEO/GEO/Search products."
        ),
        legacy_pricing_present=True,
    ),
    MrrRecoveryProduct(
        key="agent_copilot",
        historical_name="Agent Co-Pilot",
        source_path="empire_os/seed_sku_products.py",
        disposition="REBUILD",
        target_family="agent_platform",
        target_phase="10",
        revenue_models=("subscription", "seat", "enterprise"),
        current_mapping=("empire_coder", "advanced_autonomy"),
        notes=(
            "Potential future governed operator/copilot product. Rebuild on "
            "current agent authority model and OBSERVE-first controls."
        ),
        legacy_pricing_present=True,
    ),
    MrrRecoveryProduct(
        key="white_label_platform",
        historical_name="White-Label EmpireOS",
        source_path="empire_os/whitelabel.py",
        disposition="REBUILD",
        target_family="channel_enterprise",
        target_phase="8",
        revenue_models=("license", "subscription", "enterprise", "reseller"),
        current_mapping=("enterprise_white_label",),
        notes=(
            "Brand/config concept survives; SQLite storage does not. Rebuild "
            "as tenant-scoped Supabase config with domain and data isolation."
        ),
    ),
    MrrRecoveryProduct(
        key="affiliate_partner_program",
        historical_name="Affiliate / Referral Program",
        source_path="empire_os/affiliate.py",
        disposition="REBUILD",
        target_family="channel_partner",
        target_phase="8",
        revenue_models=("affiliate", "revenue_share", "reseller"),
        current_mapping=("enterprise_white_label", "partner_network"),
        notes=(
            "Recover attribution/commission concepts only after canonical "
            "Revenue Truth so commissions are based on verified realized "
            "commercial events rather than legacy invoices."
        ),
        legacy_pricing_present=True,
    ),
    MrrRecoveryProduct(
        key="omega_evaluation_mrr",
        historical_name="Omega Evaluation / Value Meter",
        source_path="docs/LEGACY_COMMERCIAL_INTELLIGENCE_RECOVERY_INDEX.md",
        disposition="REBUILD",
        target_family="scoring_intelligence",
        target_phase="8",
        revenue_models=("usage", "credit_pack", "performance", "subscription"),
        current_mapping=("omega_evaluation",),
        notes=(
            "Rebuild on Omega 2, canonical usage metering, verified outcomes, "
            "USDT/BSC and Revenue Truth."
        ),
    ),
    MrrRecoveryProduct(
        key="intelligence_retainer",
        historical_name="Hourly Intelligence Retainer",
        source_path="docs/LEGACY_COMMERCIAL_INTELLIGENCE_RECOVERY_INDEX.md",
        disposition="REBUILD",
        target_family="high_touch_intelligence",
        target_phase="8",
        revenue_models=("hourly", "retainer", "subscription"),
        current_mapping=("intel_hourly", "managed_growth"),
        notes=(
            "Product concept survives. Historical $150/hour is legacy only "
            "until a fresh governed pricing decision is approved."
        ),
        legacy_pricing_present=True,
    ),
)


def mrr_recovery_catalog() -> list[dict[str, Any]]:
    return [row.as_dict() for row in MRR_RECOVERY_PRODUCTS]


def mrr_recovery_summary() -> dict[str, Any]:
    by_disposition: dict[str, int] = {}
    by_phase: dict[str, int] = {}
    for row in MRR_RECOVERY_PRODUCTS:
        by_disposition[row.disposition] = (
            by_disposition.get(row.disposition, 0) + 1
        )
        by_phase[row.target_phase] = by_phase.get(row.target_phase, 0) + 1

    return {
        "schema_version": "empire.mrr-product-recovery.v1",
        "product_count": len(MRR_RECOVERY_PRODUCTS),
        "by_disposition": dict(sorted(by_disposition.items())),
        "by_target_phase": dict(sorted(by_phase.items())),
        "legacy_pricing_present_count": sum(
            row.legacy_pricing_present
            for row in MRR_RECOVERY_PRODUCTS
        ),
        "legacy_pricing_approved_current_count": 0,
        "legacy_settlement_allowed": False,
        "canonical_settlement_rail": "USDT_BSC",
        "actual_revenue": False,
        "execution_authority": "none",
    }
