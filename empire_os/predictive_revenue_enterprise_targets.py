"""Curated Predictive Revenue enterprise account review queue.

This module contains only public, evidence-backed account research. It prepares
internal account review material and grants no outreach, contracting, payment,
or revenue authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class EnterpriseTarget:
    account_key: str
    account_name: str
    account_type: str
    wave: str
    observed_scale: tuple[str, ...]
    observed_triggers: tuple[str, ...]
    observed_people: tuple[dict[str, str], ...]
    target_roles: tuple[str, ...]
    target_product_codes: tuple[str, ...]
    campaign_angle: str
    evidence_urls: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.update(
            {
                "evidence_classification": "PUBLIC_OBSERVED_EVIDENCE",
                "fit_classification": "INTERNAL_HYPOTHESIS",
                "budget_verified": False,
                "binding_intent_verified": False,
                "contact_verified": False,
                "commercial_terms_verified": False,
                "outreach_authorized": False,
                "payment_action": False,
                "actual_revenue": False,
                "execution_authority": "none",
            }
        )
        return payload


TARGETS: tuple[EnterpriseTarget, ...] = (
    EnterpriseTarget(
        account_key="apex_service_partners",
        account_name="Apex Service Partners",
        account_type="multi_brand_home_services_platform",
        wave="direct_enterprise",
        observed_scale=(
            "national HVAC, plumbing and electrical platform",
            "partner-services model with shared technology, analytics and data engineering",
        ),
        observed_triggers=(
            "explicit investment in technology, analytics and data engineering",
            "2026 strategic minority investment to support continued national expansion and technology infrastructure",
        ),
        observed_people=(
            {"name": "AJ Brown", "title": "Co-Chief Executive Officer"},
            {"name": "Will Matson", "title": "Co-Chief Executive Officer"},
        ),
        target_roles=(
            "chief executive officer",
            "chief marketing officer",
            "chief information officer",
            "head of analytics",
        ),
        target_product_codes=(
            "predictive_revenue_intelligence_os",
            "predictive_revenue_private_strategic",
        ),
        campaign_angle=(
            "Unify partner-level demand, marketing, call-center and market signals "
            "into a cross-brand Predictive Revenue layer that highlights where growth "
            "is likely, where capacity is constrained and which local brands need action."
        ),
        evidence_urls=(
            "https://apexservicepartners.com/",
            "https://apexservicepartners.com/who-we-are/",
            "https://www.apollo.com/wealth/insights-news/pressreleases/2026/05/apex-service-partners-and-alpine-investors-announce-strategic-mi",
        ),
    ),
    EnterpriseTarget(
        account_key="redwood_services",
        account_name="Redwood Services",
        account_type="multi_brand_home_services_platform",
        wave="direct_enterprise",
        observed_scale=(
            "national essential home-services platform",
            "partner support model driven by KPIs, coaching and cross-market collaboration",
        ),
        observed_triggers=(
            "public data-driven decision model based on proven KPIs",
            "2026 acquisition of Sierra platform expanded Redwood into new markets",
        ),
        observed_people=(
            {"name": "Richard Lewis", "title": "Chief Executive Officer & Founder"},
            {"name": "Raj Midha", "title": "Chief Marketing Officer"},
            {"name": "Shayne Mehringer", "title": "Chief Information Officer"},
        ),
        target_roles=(
            "chief executive officer",
            "chief marketing officer",
            "chief information officer",
            "operations leadership",
        ),
        target_product_codes=(
            "predictive_revenue_intelligence_os",
            "predictive_revenue_private_strategic",
        ),
        campaign_angle=(
            "Extend Redwood's KPI discipline into forward-looking partner-company "
            "revenue forecasts, opportunity detection and cross-market demand intelligence "
            "that helps the support center identify issues and opportunities earlier."
        ),
        evidence_urls=(
            "https://redwoodservices.com/",
            "https://redwoodservices.com/team/",
            "https://redwoodservices.com/news/redwood-services-expands-national-footprint-with-acquisition-of-sierra-platform-from-se-capital/",
        ),
    ),
    EnterpriseTarget(
        account_key="neighborly",
        account_name="Neighborly",
        account_type="franchise_home_services_network",
        wave="direct_enterprise",
        observed_scale=(
            "30+ brands and 5,500 franchise locations",
            "14 million+ customers stated on current leadership page",
        ),
        observed_triggers=(
            "2026 promotion created EVP Strategic Operations & Analytics remit spanning data analytics and consumer insights",
            "2026 launch of redesigned AI-powered customer app",
            "2026 CFO announcement references connecting a 26 million household customer database through marketing automation",
        ),
        observed_people=(
            {"name": "Tanner Stutz", "title": "Executive Vice President, Strategic Operations & Analytics"},
            {"name": "Stacy Lynn Bourgeois", "title": "Chief Marketing Officer"},
            {"name": "Mike Davis", "title": "Chief Executive Officer"},
        ),
        target_roles=(
            "executive vice president strategic operations and analytics",
            "chief marketing officer",
            "chief executive officer",
            "consumer insights leadership",
        ),
        target_product_codes=(
            "predictive_revenue_autonomous_os",
            "predictive_revenue_private_strategic",
        ),
        campaign_angle=(
            "Connect franchise scorecards, customer/consumer signals, marketing automation "
            "and cross-brand demand into a network-level Predictive Revenue layer that can "
            "surface leading indicators before weekly sales movement becomes obvious."
        ),
        evidence_urls=(
            "https://www.neighborlybrands.com/press-center/news/2026/neighborly-promotes-tanner-stutz-to-executive-vice-president-strategic-operations-analytics/",
            "https://www.neighborlybrands.com/press-center/news/2026/neighborly-launches-redesigned-ai-powered-app/",
            "https://www.neighborlybrands.com/press-center/news/2026/neighborly-appoints-brent-korb-as-chief-financial-officer/",
        ),
    ),
    EnterpriseTarget(
        account_key="authority_brands",
        account_name="Authority Brands",
        account_type="franchise_home_services_network",
        wave="direct_enterprise",
        observed_scale=(
            "15 home-service franchisors",
            "more than 1,000 franchise owners",
            "more than $2 billion in company-reported revenue",
        ),
        observed_triggers=(
            "advanced technology and central marketing are explicit franchise support capabilities",
            "growth and transformation leadership spans franchise development, call-center operations and acquisition integration",
        ),
        observed_people=(
            {"name": "Jay Caiafa", "title": "Chief Executive Officer"},
            {"name": "Ryan Bowes", "title": "Chief Growth and Transformation Officer"},
        ),
        target_roles=(
            "chief growth and transformation officer",
            "chief executive officer",
            "call center operations leadership",
            "marketing leadership",
        ),
        target_product_codes=(
            "predictive_revenue_autonomous_os",
            "predictive_revenue_private_strategic",
        ),
        campaign_angle=(
            "Create one governed intelligence layer across brands and territories to "
            "compare demand, call-center conversion, growth capacity and revenue opportunity "
            "without flattening the economics of individual franchise systems."
        ),
        evidence_urls=(
            "https://www.authoritybrands.com/",
            "https://www.authoritybrands.com/leadership-team/",
        ),
    ),
    EnterpriseTarget(
        account_key="sila_services",
        account_name="Sila Services",
        account_type="multi_brand_home_services_platform",
        wave="direct_enterprise",
        observed_scale=(
            "40+ brands in portfolio",
            "2,500+ team members and 1 million+ customers served on current company site",
        ),
        observed_triggers=(
            "company describes data-driven insights as part of its operating model",
            "current leadership includes CRO, CTO and CMO functions",
            "continued multi-brand expansion during 2026",
        ),
        observed_people=(
            {"name": "Ryan Flaherty", "title": "Chief Revenue Officer"},
            {"name": "Keith Chisholm", "title": "Chief Technology Officer"},
            {"name": "Lara Drake", "title": "Chief Marketing Officer"},
        ),
        target_roles=(
            "chief revenue officer",
            "chief technology officer",
            "chief marketing officer",
            "operations leadership",
        ),
        target_product_codes=(
            "predictive_revenue_intelligence_os",
            "predictive_revenue_autonomous_os",
        ),
        campaign_angle=(
            "Give Revenue, Technology and Marketing one common evidence layer for "
            "cross-brand forecasting, demand generation, customer-journey signals and "
            "market-level opportunity detection."
        ),
        evidence_urls=(
            "https://silaservices.com/",
            "https://silaservices.com/leadership/",
            "https://silaservices.com/we-are-sila/",
        ),
    ),
    EnterpriseTarget(
        account_key="turnpoint_services",
        account_name="TurnPoint Services",
        account_type="multi_brand_home_services_platform",
        wave="direct_enterprise",
        observed_scale=(
            "national residential HVAC, plumbing and electrical services platform",
            "60+ local brands and 6,000+ team members stated on current executive page",
        ),
        observed_triggers=(
            "new chief executive officer appointed in 2026 for next phase of growth and value creation",
            "new chief marketing officer appointed in 2026 to lead growth, acquisition and retention",
        ),
        observed_people=(
            {"name": "Greg Bochicchio", "title": "Chief Executive Officer"},
            {"name": "Ellen Donahue-Dalton", "title": "Chief Marketing Officer"},
            {"name": "Jeff McCall", "title": "President and Chief Operating Officer"},
        ),
        target_roles=(
            "chief marketing officer",
            "president and chief operating officer",
            "chief executive officer",
            "information leadership",
        ),
        target_product_codes=(
            "predictive_revenue_intelligence_os",
            "predictive_revenue_autonomous_os",
        ),
        campaign_angle=(
            "Support the new growth leadership team with a multi-brand revenue command "
            "layer combining acquisition, retention, demand, operational capacity and "
            "forecast signals across local brands."
        ),
        evidence_urls=(
            "https://www.turnpointservices.com/news/press-release/",
            "https://www.turnpointservices.com/news/chro-cmo-press-release/",
            "https://www.turnpointservices.com/about-us/executive-team/",
        ),
    ),
    EnterpriseTarget(
        account_key="blackstone_operating_team",
        account_name="Blackstone Operating Team",
        account_type="private_equity_operating_team",
        wave="sponsor_enterprise",
        observed_scale=(
            "operating platform supports 270+ portfolio companies on current Operating Team page",
            "dedicated data science, investment intelligence and applied AI capabilities",
        ),
        observed_triggers=(
            "Blackstone explicitly uses predictive and analytical models with portfolio companies",
            "portfolio operations leadership includes AI transformation and data science",
        ),
        observed_people=(
            {"name": "Rodney Zemmel", "title": "Global Head of Blackstone Operating Team"},
            {"name": "Matt Katz", "title": "Global Head of Data Science"},
        ),
        target_roles=(
            "global head of portfolio operations",
            "global head of data science",
            "portfolio operations",
            "investment intelligence and applied AI",
        ),
        target_product_codes=(
            "predictive_revenue_diagnostic",
            "predictive_revenue_private_strategic",
        ),
        campaign_angle=(
            "Use a selected portfolio company as a controlled Predictive Revenue diagnostic "
            "and calibration pilot, then measure whether the same evidence model transfers "
            "across comparable portfolio companies before proposing broader deployment."
        ),
        evidence_urls=(
            "https://www.blackstone.com/our-businesses/blackstone-operating-team/",
            "https://www.blackstone.com/data-science/",
            "https://www.blackstone.com/people/matt-katz/",
        ),
    ),
    EnterpriseTarget(
        account_key="vista_equity_partners",
        account_name="Vista Equity Partners",
        account_type="private_equity_operating_team",
        wave="sponsor_enterprise",
        observed_scale=(
            "85+ portfolio companies on current portfolio page",
            "portfolio-wide software operating data and AI measurement program",
        ),
        observed_triggers=(
            "2026 report measures AI impact through revenue growth and margin expansion",
            "Vista highlights an industry measurement gap for scaled AI usage and ROI",
        ),
        observed_people=(
            {"name": "Monti Saroya", "title": "Senior Managing Director, Co-Head of Flagship Fund"},
        ),
        target_roles=(
            "portfolio operations",
            "AI operating leadership",
            "value creation leadership",
            "flagship fund leadership",
        ),
        target_product_codes=(
            "predictive_revenue_diagnostic",
            "predictive_revenue_private_strategic",
        ),
        campaign_angle=(
            "Position Predictive Revenue as a portfolio-company revenue measurement and "
            "calibration layer: forecast versus actual, monetization evidence, commercial "
            "bottlenecks and repeatable value-creation reporting."
        ),
        evidence_urls=(
            "https://www.vistaequitypartners.com/insights/ai-impact-vista-portfolio-2026-mid-year-report/",
            "https://www.vistaequitypartners.com/about/companies/",
        ),
    ),
    EnterpriseTarget(
        account_key="eqt",
        account_name="EQT",
        account_type="private_equity_operating_team",
        wave="sponsor_enterprise",
        observed_scale=(
            "global private-markets platform with dedicated Motherbrain AI and data team",
            "AI and data embedded across investment and portfolio value creation",
        ),
        observed_triggers=(
            "2026 Value Creation Day focused on AI-driven operational performance and growth",
            "Motherbrain explicitly supports portfolio-company transformation with data and AI",
        ),
        observed_people=(
            {"name": "Per Franzén", "title": "Chief Executive Officer & Managing Partner"},
        ),
        target_roles=(
            "digital and AI team",
            "Motherbrain leadership",
            "portfolio value creation",
            "chief executive officer",
        ),
        target_product_codes=(
            "predictive_revenue_diagnostic",
            "predictive_revenue_private_strategic",
        ),
        campaign_angle=(
            "Offer a bounded portfolio-company pilot that adds revenue forecasting, market "
            "opportunity and prediction-versus-actual calibration to an existing AI/value-creation "
            "program without replacing internal Motherbrain capabilities."
        ),
        evidence_urls=(
            "https://eqtgroup.com/about/motherbrain",
            "https://eqtgroup.com/news/invitation-to-eqts-value-creation-day-2026-2026-04-09",
        ),
    ),
)


def build_enterprise_target_review() -> dict[str, Any]:
    """Return a deterministic internal review queue with zero execution authority."""
    rows = [target.as_dict() for target in TARGETS]
    return {
        "schema_version": "empire.predictive-revenue-enterprise-targets.v1",
        "status": "INTERNAL_REVIEW_ONLY",
        "generated_from": "public_company_evidence",
        "target_count": len(rows),
        "targets": rows,
        "truth_rules": {
            "public_fit_is_buyer_intent": False,
            "named_role_is_contact_verification": False,
            "reply_is_revenue": False,
            "meeting_is_revenue": False,
            "payment_request_is_revenue": False,
            "synthetic_targets_allowed": False,
        },
        "outreach_authorized": False,
        "payment_action": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }
