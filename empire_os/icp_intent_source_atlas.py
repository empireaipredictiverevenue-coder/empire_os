"""Evidence-governed ICP source atlas for EmpireOS revenue intelligence.

A source is a research location, never consent for contact or proof of
purchasing demand. Only Reddit's existing public RSS collector is automatic.
Other communities stay manual/review-only until lawful access is proven.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class IcpSource:
    source_id: str
    audience: str
    venue: str
    url: str
    access: str
    automation_state: str
    problem: str
    offer_key: str
    priority: int
    reddit_subreddit: str = ""
    reddit_query: str = ""
    niche: str = ""
    geography: str = ""
    evidence_basis: str = "public_community_page"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["outbound_authorized"] = False
        d["social_contact_verified"] = False
        d["buyer_budget_verified"] = False
        return d


SOURCES: tuple[IcpSource, ...] = (
    IcpSource(
        "reddit_roofing_sales", "roofing_contractors", "Reddit",
        "https://www.reddit.com/r/RoofingSales/",
        "public_reddit_rss", "OBSERVE", "lead_cost_and_conversion",
        "predictive_revenue_demand_engine", 100,
        "RoofingSales", "marketing leads", "roofing", "US",
    ),
    IcpSource(
        "reddit_roofing", "roofing_contractors", "Reddit",
        "https://www.reddit.com/r/Roofing/",
        "public_reddit_rss", "OBSERVE", "organic_roofing_leads",
        "search_growth_command", 98,
        "Roofing", "need more leads", "roofing", "US",
    ),
    IcpSource(
        "reddit_leadgen_marketplace", "roofing_lead_buyers", "Reddit",
        "https://www.reddit.com/r/LeadGenMarketplace/",
        "public_reddit_rss", "OBSERVE", "buying_roofing_calls",
        "predictive_revenue_demand_engine", 97,
        "LeadGenMarketplace", "roofing leads", "roofing", "US",
    ),
    IcpSource(
        "reddit_hvacpeople", "hvac_contractors", "Reddit",
        "https://www.reddit.com/r/hvacpeople/",
        "public_reddit_rss", "OBSERVE", "hvac_lead_cost",
        "search_growth_command", 94,
        "hvacpeople", "lead generation", "hvac", "US",
    ),
    IcpSource(
        "reddit_lawfirm", "law_firms", "Reddit",
        "https://www.reddit.com/r/LawFirm/",
        "public_reddit_rss", "OBSERVE", "legal_client_acquisition",
        "search_growth_command", 93,
        "LawFirm", "marketing clients", "law", "US",
    ),
    IcpSource(
        "reddit_smallbusinessuk", "uk_smb", "Reddit",
        "https://www.reddit.com/r/smallbusinessuk/",
        "public_reddit_rss", "OBSERVE", "b2b_lead_generation",
        "revenue_conversion_system", 91,
        "smallbusinessuk", "leads sales", "b2b", "UK",
    ),
    IcpSource(
        "reddit_smallbusiness", "smb_owners", "Reddit",
        "https://www.reddit.com/r/smallbusiness/",
        "public_reddit_rss", "OBSERVE", "lead_generation",
        "revenue_conversion_system", 83,
        "smallbusiness", "lead generation", "b2b", "online",
    ),
    IcpSource(
        "reddit_entrepreneur", "smb_founders", "Reddit",
        "https://www.reddit.com/r/Entrepreneur/",
        "public_reddit_rss", "OBSERVE", "growth_and_sales",
        "predictive_revenue", 79,
        "Entrepreneur", "customer acquisition", "b2b", "online",
    ),
    IcpSource(
        "reddit_solar_business", "solar_contractors", "Reddit",
        "https://www.reddit.com/r/Solarbusiness/",
        "public_reddit_rss", "OBSERVE", "solar_lead_generation",
        "predictive_revenue_demand_engine", 90,
        "Solarbusiness", "lead generation", "solar", "US",
    ),
    IcpSource(
        "reddit_agency", "seo_agencies", "Reddit",
        "https://www.reddit.com/r/agency/",
        "public_reddit_rss", "OBSERVE", "agency_churn_and_client_acquisition",
        "predictive_revenue", 86,
        "agency", "client acquisition", "agency", "online",
    ),
    IcpSource(
        "reddit_localseo", "local_seo_agencies", "Reddit",
        "https://www.reddit.com/r/localseo/",
        "public_reddit_rss", "OBSERVE", "local_search_reporting",
        "search_growth_command", 85,
        "localseo", "client leads", "agency", "online",
    ),
    IcpSource(
        "reddit_dentistry", "dental_practice_owners", "Reddit",
        "https://www.reddit.com/r/Dentistry/",
        "public_reddit_rss", "OBSERVE", "patient_acquisition_and_marketing_roi",
        "predictive_revenue_demand_engine", 92,
        "Dentistry", "new patients marketing", "dental", "US",
    ),
    IcpSource(
        "reddit_saas", "saas_founders", "Reddit",
        "https://www.reddit.com/r/SaaS/",
        "public_reddit_rss", "OBSERVE", "first_customers_and_retention",
        "predictive_revenue", 89,
        "SaaS", "struggling get customers", "saas", "online",
    ),
    IcpSource(
        "alignable_marketing", "us_ca_smb_owners", "Alignable",
        "https://www.alignable.com/groups/marketing-for-the-small-business",
        "public_view_only", "MANUAL_REVIEW_ONLY", "marketing_growth",
        "search_growth_command", 92,
        evidence_basis="public_group_rules_no_solicitation",
    ),
    IcpSource(
        "alignable_leads", "us_ca_smb_owners", "Alignable",
        "https://www.alignable.com/groups/small-business-lead-generation",
        "public_view_only", "MANUAL_REVIEW_ONLY", "lead_generation",
        "predictive_revenue_demand_engine", 89,
        evidence_basis="public_group_rules_no_solicitation",
    ),
    IcpSource(
        "afflift_pay_per_call", "publisher_networks", "affLIFT",
        "https://afflift.com/f/forums/pay-per-call.51/",
        "public_index_and_member_sections", "MANUAL_REVIEW_ONLY",
        "call_supply_and_publisher_terms",
        "predictive_revenue_demand_engine", 96,
        evidence_basis="forum_has_login_gated_sections",
    ),
)

REDDIT_ROTATION: tuple[tuple[str, str, str, str], ...] = tuple(
    (r.reddit_subreddit, r.reddit_query, r.niche, r.geography)
    for r in SOURCES
    if r.automation_state == "OBSERVE" and r.access == "public_reddit_rss"
)


def atlas_summary() -> dict[str, Any]:
    return {
        "schema_version": "empire.icp_research_sources.v1",
        "mode": "OBSERVE",
        "source_count": len(SOURCES),
        "automatic_public_rss_sources": len(REDDIT_ROTATION),
        "manual_review_only_sources": sum(
            r.automation_state == "MANUAL_REVIEW_ONLY" for r in SOURCES
        ),
        "venue_policy": "respect_robots_terms_and_group_rules",
        "private_or_login_gated_scraping_enabled": False,
        "auto_contact_enabled": False,
        "outbound_authorized": False,
        "execution_authority": "NONE",
        "sources": [row.to_dict() for row in SOURCES],
    }
