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