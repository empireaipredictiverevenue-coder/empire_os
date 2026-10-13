"""Bounded, sourced public-site market-role research for enterprise review.

Observed offers/acquisitions are not proof of procurement demand or intent.
These analyst hypotheses never overwrite scout product mappings or grant send.
"""
from __future__ import annotations

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
        "related_seed_account_keys_for_dedup_review_only": ["blackstone_operating_team"],
        "next_research_action": "Validate revenue forecasting pain, group-level systems, potential Blackstone account overlap and relevant commercial owner",
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
        **evidence,
        "reviewed_on": "2026-10-13",
        "evidence_class": "PUBLIC_FIRST_PARTY_SITE_OBSERVATION",
        "verified_buying_intent": False,
        "outreach_authorized": False,
    }
