"""Bounded, sourced public-site market-role research for enterprise review.

Observed offers/acquisitions are not proof of procurement demand or intent.
These analyst hypotheses never overwrite scout product mappings or grant send.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

# Official company website evidence reviewed 2026-10-13. This list is not a
# universal industry classifier and has no authority beyond internal review.
PUBLIC_MARKET_ROLE_RESEARCH: dict[str, dict[str, Any]] = {
    "championsgroupholdings.com": {
        "role_hypothesis": "OPERATING_END_CUSTOMER_HYPOTHESIS",
        "review_lane": "CUSTOMER_DISCOVERY",
        "observations": [
            {
                "fact": "Announced acquisition of Powell Electric on 2026-08-07",
                "source_url": "https://championsgroupholdings.com/2026/08/07/champions-group-expands-southern-california-footprint-with-acquisition-of-powell-electric/",
            },
            {
                "fact": "Blackstone announced a definitive agreement to acquire Champions Group on 2026-02-17; closing not independently verified",
                "source_url": "https://championsgroupholdings.com/2026/02/17/excited-to-share-an-important-next-chapter-for-champions-group/",
            },
            {
                "fact": "Published further acquisition and expansion updates in 2026",
                "source_url": "https://championsgroupholdings.com/news/",
            },
        ],
        "reason": "Home-services multi-brand expansion creates a testable forecasting and integration use case",
        "suggested_product_codes_for_review_only": ["predictive_revenue_diagnostic"],
        "testable_discovery_questions": [
            "Can cross-brand lead-to-booked-job conversion be measured consistently?",
            "Where do appointment capacity and local demand fail to match by market?",
            "Can marketing investment and retention be compared across acquired brands?",
        ],
        "economic_impact_not_yet_measured": True,
        "related_seed_account_keys_for_dedup_review_only": ["blackstone_operating_team"],
        "public_contact_routes_for_review_only": [
            {
                "published_email": "Partnerships@championsgh.com",
                "source_url": "https://championsgroupholdings.com/contact/",
                "route_context": "Home-services partner enquiry form requests service trade and truck count",
                "software_vendor_fit_verified": False,
                "person_bound": False,
                "recipient_suppression_cleared": False,
                "outreach_authorized": False,
            },
        ],
        "observed_buyer_roles_for_review_only": [
            {"name": "Laura Koester", "title": "Chief Marketing Officer",
             "source_url": "https://championsgroupholdings.com/our-leadership/",
             "public_professional_profile": "https://www.linkedin.com/in/laurakoester2",
             "profile_is_recipient_consent": False,
             "person_email_binding_verified": False},
            {"name": "Frank DiMarco", "title": "Chief Executive Officer",
             "source_url": "https://championsgroupholdings.com/our-leadership/",
             "person_email_binding_verified": False},
        ],
        "next_research_action": "Verify CFO/CMO business need and an appropriate vendor route; the published partnerships inbox may concern trade acquisitions, not software purchases",
    },
    "technomile.com": {
        "role_hypothesis": "COMPETITIVE_PRODUCT_OVERLAP",
        "review_lane": "COMPETITOR_OR_PARTNER_RESEARCH",
        "observations": [
            {
                "fact": "Offers government-contractor Growth CRM, AI capture and GovSearchAI opportunity intelligence",
                "source_url": "https://technomile.com/products/growth-suite",
            },
        ],
        "reason": "Direct product-function overlap makes generic opportunity-intelligence sales pitch weak",
        "suggested_product_codes_for_review_only": [],
        "next_research_action": "Identify a differentiated data corridor or authorised partnership need before any sales qualification",
    },
    "exlservice.com": {
        "role_hypothesis": "COMPETITIVE_SERVICE_OVERLAP",
        "review_lane": "COMPETITOR_OR_PARTNER_RESEARCH",
        "observations": [
            {
                "fact": "Markets analytics, decision intelligence, AI governance and implementation services",
                "source_url": "https://www.exlservice.com/services-and-solutions/ai-services",
            },
            {
                "fact": "Announced expanded agentic AI and decision intelligence portfolio on 2026-03-11",
                "source_url": "https://ir.exlservice.com/news-releases/news-release-details/exl-unveils-new-agentic-ai-solutions-accelerate-enterprise",
            },
        ],
        "reason": "Substantial services and decision-intelligence overlap requires a differentiated partner hypothesis",
        "suggested_product_codes_for_review_only": [],
        "next_research_action": "Research non-overlapping partner use cases; do not present as an authenticated software buyer",
    },
}


def market_role_review(domain: str) -> dict[str, Any]:
    """Return a sourced hypothesis, never an authenticated commercial status."""
    key = str(domain or "").strip().lower()
    evidence = PUBLIC_MARKET_ROLE_RESEARCH.get(key)
    if evidence is None:
        return {
            "role_hypothesis": "UNCLASSIFIED_RESEARCH",
            "review_lane": "GENERAL_RESEARCH",
            "observations": [],
            "reason": "No independent market-role review recorded",
            "suggested_product_codes_for_review_only": [],
            "next_research_action": "Verify customer versus vendor role",
            "verified_buying_intent": False,
            "outreach_authorized": False,
        }
    return {
        **deepcopy(evidence),
        "reviewed_on": "2026-10-13",
        "evidence_class": "PUBLIC_FIRST_PARTY_SITE_OBSERVATION",
        "verified_buying_intent": False,
        "outreach_authorized": False,
    }
