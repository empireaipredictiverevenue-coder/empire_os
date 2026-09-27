"""Read-only recovered marketing and GTM portfolio.

This module converts canonical marketing blueprints and salvaged GTM patterns
into structured operating plans. It does not publish, spend, send outreach,
create binding offers or mutate commercial state.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


VALID_STATES = {
    "ACTIVE_BUILD",
    "INCUBATE",
    "SALVAGE_CANDIDATE",
    "REFERENCE_ONLY",
}


@dataclass(frozen=True)
class MarketingPlan:
    key: str
    name: str
    state: str
    product_keys: tuple[str, ...]
    icps: tuple[str, ...]
    triggers: tuple[str, ...]
    channels: tuple[str, ...]
    assets: tuple[str, ...]
    primary_cta: str
    proof_requirements: tuple[str, ...]
    notes: str = ""
    execution_authority: str = "none"
    outbound_authority: bool = False
    publishing_authority: bool = False
    paid_spend_authority: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


MARKETING_PLANS: tuple[MarketingPlan, ...] = (
    MarketingPlan(
        key="predictive_revenue_category",
        name="Predictive Revenue Category Campaign",
        state="ACTIVE_BUILD",
        product_keys=("predictive_revenue", "market_revenue_gps"),
        icps=("revenue_leader", "growth_leader", "enterprise", "agency"),
        triggers=("planning_cycle", "forecast_gap", "tool_fragmentation"),
        channels=("website", "search", "content", "demo", "partner", "governed_outbound"),
        assets=("category_landing", "revenue_gps_demo", "world_model_visual", "outcome_loop_explainer"),
        primary_cta="Review where profitable revenue is emerging next.",
        proof_requirements=("observed_product_evidence", "no_forecast_as_result"),
    ),
    MarketingPlan(
        key="permit_opportunity_gtm",
        name="Permits Before Prospects",
        state="ACTIVE_BUILD",
        product_keys=("permit_intelligence", "permit_intelligence_feed"),
        icps=("contractor", "agency", "supplier", "property_operator", "private_capital"),
        triggers=("new_permit", "permit_trend", "territory_activity", "project_signal"),
        channels=("free_tool", "search", "report", "partner", "governed_outbound", "api_trial"),
        assets=("permit_opportunity_checker", "permit_trend_report", "permit_radar_demo", "territory_alert_preview"),
        primary_cta="See permit-backed opportunity in your market before generic lead lists.",
        proof_requirements=("observed_permit_record", "source_provenance", "freshness"),
    ),
    MarketingPlan(
        key="property_portfolio_gtm",
        name="Property Opportunity & Portfolio Intelligence",
        state="ACTIVE_BUILD",
        product_keys=("property_intelligence", "property_intelligence_monitor"),
        icps=("property_operator", "facilities_team", "developer", "investor", "contractor", "lender"),
        triggers=("permit_change", "storm_event", "portfolio_change", "asset_condition_signal", "expansion"),
        channels=("report", "portfolio_brief", "search", "partner", "governed_outbound", "demo"),
        assets=("portfolio_heatmap", "property_opportunity_brief", "multi_site_monitor_preview", "trigger_report"),
        primary_cta="Review the highest-evidence property opportunities across your portfolio or territory.",
        proof_requirements=("canonical_property_or_site", "source_provenance", "observed_trigger"),
    ),
    MarketingPlan(
        key="private_capital_abm",
        name="Private Capital Sponsor & Roll-Up ABM",
        state="ACTIVE_BUILD",
        product_keys=("private_capital_rollup", "private_capital_intelligence"),
        icps=("private_equity_sponsor", "operating_partner", "independent_sponsor", "portfolio_company"),
        triggers=("platform_strategy", "add_on_search", "portfolio_growth", "market_fragmentation", "corporate_change"),
        channels=("account_brief", "research_report", "partner", "governed_outbound", "executive_demo", "api_trial"),
        assets=("rollup_market_map", "add_on_opportunity_brief", "portfolio_growth_brief", "sponsor_intelligence_demo"),
        primary_cta="Review the markets, add-ons and growth signals Empire can evidence across the portfolio.",
        proof_requirements=("canonical_company_or_sponsor", "source_provenance", "no_inferred_deal_intent"),
    ),
    MarketingPlan(
        key="storm_home_services_gtm",
        name="Storm / Home Services Revenue Strike",
        state="ACTIVE_BUILD",
        product_keys=("storm_weather_intelligence", "managed_growth"),
        icps=("roofing", "restoration", "hvac", "home_services_buyer"),
        triggers=("verified_storm_event", "territory_exposure", "buyer_capacity", "property_signal"),
        channels=("opportunity_brief", "governed_outbound", "partner", "search", "landing", "demo"),
        assets=("storm_opportunity_brief", "territory_map", "buyer_capacity_cta", "founding_partner_pack"),
        primary_cta="Review evidence-backed demand in a territory you can actually serve.",
        proof_requirements=("verified_event", "real_company", "fresh_contact_evidence", "no_fake_scarcity"),
    ),
    MarketingPlan(
        key="search_growth_gtm",
        name="Search / AEO / GEO Growth GTM",
        state="ACTIVE_BUILD",
        product_keys=("search_intelligence_suite",),
        icps=("growth_team", "agency", "multi_location", "enterprise"),
        triggers=("visibility_gap", "citation_gap", "technical_issue", "competitor_gap"),
        channels=("free_tool", "search", "content", "report", "demo", "partner"),
        assets=("ai_visibility_checker", "search_opportunity_report", "competitor_gap_report", "search_command_demo"),
        primary_cta="See the evidence-backed search and AI visibility gaps worth fixing first.",
        proof_requirements=("observed_search_evidence", "no_invented_rankings", "no_invented_traffic"),
    ),
    MarketingPlan(
        key="enterprise_white_label_gtm",
        name="Enterprise / White-Label / Partner GTM",
        state="ACTIVE_BUILD",
        product_keys=("enterprise_white_label",),
        icps=("enterprise", "agency", "reseller", "data_buyer", "strategic_partner"),
        triggers=("multi_client_need", "data_integration_need", "territory_scale", "portfolio_scale"),
        channels=("partner", "account_brief", "executive_demo", "api_trial", "governed_outbound"),
        assets=("white_label_demo", "partner_pack", "api_data_sample", "enterprise_architecture_brief"),
        primary_cta="Evaluate Empire intelligence as an embedded data, workflow or white-label capability.",
        proof_requirements=("current_product_readiness", "current_terms", "verified_capabilities"),
    ),
    MarketingPlan(
        key="roofing_founding_partner_salvage",
        name="Roofing Founding Partner Campaign",
        state="SALVAGE_CANDIDATE",
        product_keys=("storm_weather_intelligence", "managed_growth"),
        icps=("roofing_contractor", "restoration_contractor"),
        triggers=("storm_event", "territory_capacity", "permit_activity"),
        channels=("governed_outbound", "partner", "opportunity_brief"),
        assets=("short_email", "followup_sequence", "territory_brief", "capacity_question"),
        primary_cta="Confirm whether the contractor can accept qualified opportunity in the territory.",
        proof_requirements=("fresh_contact", "fresh_event_evidence", "real_availability", "compliant_opt_out"),
        notes="Recover framing/cadence only; legacy contact lists and old claims are not trusted.",
    ),
    MarketingPlan(
        key="partner_agency_distribution",
        name="Agency / Partner Distribution",
        state="ACTIVE_BUILD",
        product_keys=("enterprise_white_label", "search_intelligence_suite", "permit_intelligence"),
        icps=("agency", "consultant", "reseller", "affiliate", "integration_partner"),
        triggers=("client_scale", "differentiation_need", "data_need", "white_label_need"),
        channels=("partner", "referral", "co_marketing", "demo", "api_trial"),
        assets=("partner_tier", "referral_pack", "white_label_demo", "co_marketing_kit", "report_generator"),
        primary_cta="Add Empire intelligence to your client delivery or distribution stack.",
        proof_requirements=("real_product_capability", "current_partner_terms"),
    ),
    MarketingPlan(
        key="oil_gas_research_gtm",
        name="Oil & Gas / Energy Infrastructure GTM Research",
        state="INCUBATE",
        product_keys=("oil_gas_intelligence",),
        icps=("operator", "oilfield_service_company", "supplier", "energy_investor", "private_capital"),
        triggers=("permit_activity", "maintenance_signal", "expansion_signal", "corporate_change"),
        channels=("research_only",),
        assets=("buyer_interview_plan", "source_map", "competitive_landscape", "sample_intelligence_brief"),
        primary_cta="Research only — no commercial CTA until buyer/source/economics validation.",
        proof_requirements=("source_rights", "buyer_validation", "compliance_review", "fulfilment_model", "economics"),
        notes="No campaign launch authority. Validate ICP, sources, buying cadence and product value first.",
    ),
)


def marketing_plan_catalog() -> list[dict[str, Any]]:
    return [plan.as_dict() for plan in MARKETING_PLANS]


def marketing_summary() -> dict[str, Any]:
    by_state: dict[str, int] = {}
    for plan in MARKETING_PLANS:
        by_state[plan.state] = by_state.get(plan.state, 0) + 1
    return {
        "schema_version": "empire.marketing-recovery.v1",
        "plan_count": len(MARKETING_PLANS),
        "by_state": dict(sorted(by_state.items())),
        "execution_authority": "none",
        "outbound_authority": False,
        "publishing_authority": False,
        "paid_spend_authority": False,
        "actual_revenue": False,
    }
