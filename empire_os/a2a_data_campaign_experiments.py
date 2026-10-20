"""Laser-specific B2B data campaigns from verified-shape research-only signals.

Creates draft experiments, not Meta Ads custom audiences, harvested contacts,
external outreach, publishing, billing or permission for data resale.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping

from empire_os.a2a_commercial_signal_miner import AGENT_ID, SCHEMA as SIGNAL_SCHEMA

SCHEMA = "empire.a2a.data_campaign_experiments.v1"

# Explicit buyer-role and product-use templates. No claims of prospect identity.
DATA_TARGETS = {
    "general_contractor": {
        "buyer_roles": ["preconstruction director", "business development director",
                        "commercial estimator", "project intelligence lead"],
        "firmographic_filters": ["operates in NYC commercial construction",
                                "uses permit/project intelligence in project decisions"],
        "exclusions": ["consumer homeowners", "non-commercial contractors",
                       "businesses outside verified licence/use geography"],
        "proof_questions": [
            "Which NYC permit and project fields do you need?",
            "What is your permitted commercial use and refresh frequency?",
            "Who approves purchases of verified project intelligence?",
        ],
        "artifact": "sample NYC permit verification report (rights pending)",
        "offer": "Evidence-linked construction project verification",
    },
    "hvac": {
        "buyer_roles": ["HVAC owner", "head of growth", "regional sales director",
                        "verified appointment buyer"],
        "firmographic_filters": ["serves the target metro", "can confirm service territories",
                                "has authority to buy market intelligence"],
        "exclusions": ["unverified lead resellers", "outside buyer-approved ZIP areas",
                       "consumer contact lists without consent"],
        "proof_questions": [
            "Which HVAC territories are commercially active?",
            "Which demand and lead-quality indicators would you buy?",
            "Do you have documented buying capacity and qualification rules?",
        ],
        "artifact": "aggregated HVAC market opportunity brief",
        "offer": "Evidence-backed HVAC territory and demand-gap intelligence",
    },
    "roofing": {
        "buyer_roles": ["roofing company owner", "market expansion lead",
                        "restoration operations director", "verified call buyer"],
        "firmographic_filters": ["operates in the relevant service territory",
                                "has capacity for additional qualified projects",
                                "buys commercial intelligence"],
        "exclusions": ["cold consumer profiles", "unverified buyer agreements",
                       "unlicensed project and storm datasets"],
        "proof_questions": [
            "Which roofing service areas and job types are priorities?",
            "What evidence of project timing and demand would you value?",
            "What verified volume, price and appointment rules do you accept?",
        ],
        "artifact": "aggregated roofing demand and service-area research brief",
        "offer": "Roofing opportunity and territory intelligence",
    },
    "predictive_revenue_enterprise": {
        "buyer_roles": ["chief revenue officer", "revenue operations leader",
                        "growth director", "commercial operations head"],
        "firmographic_filters": ["B2B pipeline with measurable funnel stages",
                                "multi-territory sales operations", "uses first-party CRM data"],
        "exclusions": ["businesses without relevant consent or usable data",
                       "individual consumer social profiles"],
        "proof_questions": [
            "What pipeline conversion failures cost the most?",
            "Which first-party events are available for measurement?",
            "Who owns the budget for decision intelligence?",
        ],
        "artifact": "original first-party predictive revenue assessment",
        "offer": "Pipeline opportunity and revenue conversion intelligence",
    },
}


def build_data_campaign_experiments(
    signal_review: Mapping[str, Any],
    *,
    max_campaigns: int = 5,
) -> dict[str, Any]:
    if not isinstance(signal_review, Mapping) or signal_review.get("schema_version") != SIGNAL_SCHEMA:
        raise ValueError("invalid_miner_report")
    if signal_review.get("agent_id") != AGENT_ID or signal_review.get("execution_authority") != "NONE":
        raise ValueError("untrusted_miner_identity_or_authority")
    if not 1 <= max_campaigns <= 10:
        raise ValueError("invalid_campaign_limit")
    if signal_review.get("outbound_sent") is not False or signal_review.get("publishing_performed") is not False:
        raise ValueError("unexpected_external_execution")
    signals = signal_review.get("prioritized_research_signals")
    if not isinstance(signals, list) or len(signals) > 100:
        raise ValueError("invalid_signal_list")
    campaigns = []
    seen_markets: set[tuple[str, str]] = set()
    for item in signals:
        if len(campaigns) >= max_campaigns:
            break
        if not isinstance(item, Mapping):
            continue
        niche, metro = item.get("niche"), item.get("metro")
        if not isinstance(niche, str) or niche not in DATA_TARGETS or not isinstance(metro, str):
            continue
        if item.get("source_domain") != "revenue_gps" or item.get("buyer_class") != "B2B_DATA_OR_INTELLIGENCE_BUYER":
            continue
        if item.get("evidence_status") != "GEO_MARKET_RESEARCH_NOT_BUYER_OR_LICENSE_PROOF":
            continue
        if (niche, metro) in seen_markets:
            continue
        seen_markets.add((niche, metro))
        target = DATA_TARGETS[niche]
        topic = item.get("offer_hypothesis")
        if topic not in {"nyc_permit_project_verification", "founder_original_intelligence_reports"}:
            continue
        slug = sha256((str(niche) + ":" + metro).encode()).hexdigest()[:14]
        location = ("New York City" if metro == "nyc" else metro.title())
        # Never present the headline as proof of a market purchase.
        value = target["offer"] + " for " + location
        campaigns.append({
            "campaign_id": f"research-only-{slug}",
            "agent_owner": AGENT_ID,
            "segment": {"vertical": niche, "metro": metro,
                        "role_titles_not_personal_identities": target["buyer_roles"],
                        "firmographic_qualification": target["firmographic_filters"],
                        "negative_filters": target["exclusions"]},
            "product_proposal": {"product_id": topic,
                                 "sample_deliverable": target["artifact"],
                                 "delivery_ready_verified": False,
                                 "data_licence_and_resale_cleared": False},
            "creative_a_draft": {
                "headline": value,
                "body": ("See which business-relevant signals should be verified before "
                         "making a growth or procurement decision in " + location + "."),
                "cta": "Request a source-and-licence review",
            },
            "creative_b_draft": {
                "headline": "Where are the intelligence gaps in " + location + "?",
                "body": ("Explore a proposed " + target["artifact"] +
                         ". Availability depends on source rights and verification."),
                "cta": "Discuss requirements",
            },
            "qualifying_questions": target["proof_questions"],
            "recommended_channel": "first_party_organic_seo_or_consent_based_partner_content",
            "prohibited_targeting": [
                "private_group_member_extraction",
                "sensitive_personal_data",
                "unconsented_custom_audiences",
                "unverified_exclusive_geo_claims",
            ],
            "experiment_plan": {
                "objective": "find 1 independently verified interested business and lawful data use",
                "sequence": [
                    "validate data rights",
                    "independently identify business suitability using permitted business sources",
                    "prepare sample with proven data rights",
                    "founder approve owned organic test",
                    "measure consented requests, qualified buyer interest, actual paid outcomes",
                ],
                "metrics": [
                    "consented_inbound_replies", "qualified_business_inquiries",
                    "evidence_backed_sample_requests", "verified_orders",
                    "net_cash_settled",
                ],
                "observed_results": None,
            },
            "research_priority_score_not_probability": item["research_priority_score_not_probability"],
            "source_research_segment_id": item["segment_id"],
            "status": "DRAFT_NEEDS_SOURCE_AND_FOUNDER_REVIEW",
            "publishing_authorised": False,
            "outbound_authorised": False,
            "spend_authorised": False,
            "pipeline_created": False,
            "payment_created": False,
        })
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE", "execution_authority": "NONE",
        "agent_id": AGENT_ID,
        "campaign_count": len(campaigns),
        "campaigns": campaigns,
        "verified_buyers": 0,
        "banking_executed": False, "payments_executed": False,
        "campaigns_launched": 0, "spend_authorised": False,
        "next_gate": "SOURCE_RIGHTS_AND_BUSINESS_QUALIFICATION_REVIEW",
    }
