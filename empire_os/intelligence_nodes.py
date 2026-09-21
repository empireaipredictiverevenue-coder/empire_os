"""Empire Intelligence Node catalogue.

Nodes are commercial intelligence domains, not individual scrapers. Each node
may consume multiple sensors and publish derived evidence/opportunities into
the shared Intelligence Fabric.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class IntelligenceNode:
    key: str
    name: str
    market: str
    sensors: tuple[str, ...]
    products: tuple[str, ...]
    opportunity_types: tuple[str, ...]
    execution_authority: str = "intelligence_only"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
NODES = (
    IntelligenceNode(
        key="home_services",
        name="Home Services Intelligence Node",
        market="contractors_and_local_services",
        sensors=(
            "overpass", "biz_search", "permits", "nws_alerts",
            "registry", "site_probe",
        ),
        products=(
            "contractor_directory", "territory_intelligence",
            "trigger_alerts", "buyer_opportunity_feed",
        ),
        opportunity_types=(
            "new_project", "storm_demand", "expansion", "buyer_capacity",
        ),
    ),
    IntelligenceNode(
        key="solar_energy",
        name="Solar & Energy Intelligence Node",
        market="solar_installers_energy_services_and_property_owners",
        sensors=(
            "overpass", "biz_search", "permits", "nws_alerts",
            "registry", "site_probe", "property_signals",
        ),
        products=(
            "solar_installer_directory", "solar_territory_intelligence",
            "property_solar_opportunity_map", "permit_trigger_alerts",
            "commercial_solar_opportunity_feed",
        ),
        opportunity_types=(
            "new_install", "retrofit", "property_fit", "installer_capacity",
            "storm_replacement", "territory_expansion",
        ),
    ),
    IntelligenceNode(
        key="hvac_climate",
        name="HVAC & Climate Services Intelligence Node",
        market="hvac_contractors_building_services_and_property_operators",
        sensors=(
            "overpass", "biz_search", "permits", "nws_alerts",
            "registry", "site_probe", "property_signals",
        ),
        products=(
            "hvac_contractor_directory", "hvac_territory_intelligence",
            "replacement_demand_signals", "weather_load_alerts",
            "building_upgrade_opportunity_feed",
        ),
        opportunity_types=(
            "replacement_cycle", "weather_demand", "new_system",
            "property_upgrade", "contractor_capacity", "territory_expansion",
        ),
    ),
    IntelligenceNode(
        key="property",
        name="Property Opportunity Node",
        market="property_and_facilities",
        sensors=(
            "permits", "chicago_311", "nyc_hpd", "nws_alerts",
            "ownership_records",
        ),
        products=(
            "property_opportunity_graph", "distress_alerts",
            "renovation_signals", "owner_intelligence",
        ),
        opportunity_types=(
            "repair_need", "renovation", "violation", "storm_damage",
        ),
    ),
    IntelligenceNode(
        key="volumetric",
        name="Volumetric Intelligence Node",
        market="property_assets_sites_terrain_and_spatial_environments",
        sensors=(
            "satellite_imagery", "drone_imagery", "lidar", "depth_maps",
            "property_geometry", "digital_twins", "site_photogrammetry",
        ),
        products=(
            "3d_asset_map", "site_geometry_intelligence",
            "spatial_change_alerts", "volumetric_opportunity_feed",
        ),
        opportunity_types=(
            "spatial_change", "property_fit", "asset_condition",
            "site_capacity", "storm_surface_change", "terrain_exposure",
        ),
    ),
    IntelligenceNode(
        key="natural_physical",
        name="Natural Physical Intelligence Node",
        market="real_world_asset_condition_and_physical_systems",
        sensors=(
            "weather_observations", "storm_signals", "thermal_imagery",
            "material_condition", "building_systems", "sensor_telemetry",
            "volumetric",
        ),
        products=(
            "physical_condition_feed", "damage_risk_intelligence",
            "energy_load_intelligence", "asset_degradation_alerts",
            "physical_opportunity_feed",
        ),
        opportunity_types=(
            "damage_response", "repair_need", "replacement_cycle",
            "energy_upgrade", "flood_exposure", "structural_risk",
            "solar_fit", "maintenance_need",
        ),
    ),
    IntelligenceNode(
        key="market_intent",
        name="Market Intent Node",
        market="cross_vertical_b2b",
        sensors=("reddit", "courtlistener", "search_fabric"),
        products=(
            "buying_intent_feed", "market_demand_index",
            "problem_trend_alerts",
        ),
        opportunity_types=(
            "active_buying_intent", "vendor_change", "commercial_problem",
        ),
    ),
    IntelligenceNode(
        key="corporate",
        name="Corporate Change Node",
        market="b2b_and_enterprise",
        sensors=("sec_edgar", "company_websites", "search_fabric"),
        products=(
            "corporate_change_feed", "growth_signals",
            "vendor_opportunity_alerts",
        ),
        opportunity_types=(
            "expansion", "capital_event", "acquisition", "operational_change",
        ),
    ),
    IntelligenceNode(
        key="private_capital",
        name="Private Capital & Roll-Up Intelligence Node",
        market="private_equity_independent_sponsors_and_portfolio_companies",
        sensors=(
            "sec_form_adv", "sec_edgar", "companies_house",
            "sponsor_portfolio_pages", "m_and_a_announcements",
            "public_registries", "property_signals", "search_fabric",
        ),
        products=(
            "private_equity_sponsor_graph", "rollup_market_map",
            "add_on_target_feed", "founder_exit_signal_feed",
            "portfolio_growth_opportunity_map", "consolidation_index",
        ),
        opportunity_types=(
            "platform_acquisition", "add_on_acquisition", "owner_exit",
            "rollup_cluster", "portfolio_cross_sell", "carve_out",
        ),
    ),
    IntelligenceNode(
        key="government",
        name="Government Spend Node",
        market="public_sector_and_suppliers",
        sensors=("usaspending", "procurement_notices", "agency_data"),
        products=(
            "award_intelligence", "incumbent_map",
            "subcontract_opportunity_feed",
        ),
        opportunity_types=(
            "new_award", "renewal_window", "supplier_gap", "subcontracting",
        ),
    ),
    IntelligenceNode(
        key="healthcare",
        name="Healthcare Growth Node",
        market="providers_and_healthcare_vendors",
        sensors=("cms_nppes", "provider_sites", "public_registries"),
        products=(
            "provider_growth_feed", "practice_change_alerts",
            "territory_intelligence",
        ),
        opportunity_types=(
            "new_provider", "new_location", "practice_growth", "vendor_need",
        ),
    ),
    IntelligenceNode(
        key="compliance",
        name="Compliance & Risk Node",
        market="industrial_and_regulated_businesses",
        sensors=("osha", "epa_echo", "public_registries"),
        products=(
            "compliance_signal_feed", "risk_change_alerts",
            "service_opportunity_feed",
        ),
        opportunity_types=(
            "inspection", "citation", "remediation_need", "compliance_change",
        ),
    ),
    IntelligenceNode(
        key="legal_mass_tort",
        name="Legal & Mass Tort Intelligence Node",
        market="plaintiff_law_firms_and_legal_marketing",
        sensors=(
            "firm_finder", "ca_bar", "tx_bar", "courtlistener",
            "reddit_mass_tort", "search_fabric", "adgen_scanner",
            "legal_aeo_pages",
        ),
        products=(
            "law_firm_directory", "mass_tort_market_map",
            "firm_buyer_intelligence", "case_demand_signals",
            "competitor_campaign_intelligence",
            "campaign_audience_feed",
        ),
        opportunity_types=(
            "firm_buyer", "active_mass_tort", "new_campaign",
            "case_demand", "competitive_gap", "intake_capacity",
        ),
    ),
)