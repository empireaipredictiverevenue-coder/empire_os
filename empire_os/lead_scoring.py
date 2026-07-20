"""AI Lead Scoring & Qualification Engine.

Uses local rule-based scoring enriched with signals from the crm_lead record.
This provides immediate value without requiring external LLM API calls.
An LLM-based re-scoring plugin point is included for when you wire up
an AI provider.

Scoring dimensions (each 0-100):
  - data_completeness  — how enriched the record is
  - business_presence  — has website, email, phone, social
  - market_fit         — niche is in our target verticals
  - engagement_potential — omega_score from lane_leads
  - enrichment_quality — number of enrichment sources that returned data

Composite score = weighted average of dimensions.
Thresholds determine tier: cold / warm / hot / qualified.
"""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("lead_scoring")

# ── Target niches (what we qualify for) ─────────────────────────────
TARGET_NICHES = {
    "roof_repair",
    "residential_roofing",
    "commercial_roofing",
    "roofing",
    "hvac",
    "hvac_repair",
    "plumbing",
    "electrical",
    "solar",
    "solar_installation",
    "general_contractor",
    "home_improvement",
    "siding",
    "windows",
    "gutter",
    "paving",
    "concrete",
    "landscaping",
    "pest_control",
    "painting",
    "flooring",
}

# Weights for each scoring dimension
WEIGHTS = {
    "data_completeness": 0.20,
    "business_presence": 0.25,
    "market_fit": 0.30,
    "engagement_potential": 0.15,
    "enrichment_quality": 0.10,
}


def score_data_completeness(lead: dict) -> float:
    """How complete is the record?"""
    score = 0.0
    checks = {
        "business_name": 15,
        "email": 15,
        "phone": 15,
        "website": 10,
        "street": 5,
        "city": 5,
        "state": 5,
        "zip": 5,
        "license_no": 10,
        "contact_name": 10,
    }
    for field, weight in checks.items():
        val = lead.get(field)
        if val and str(val).strip() and str(val) not in ("[]", "{}", ""):
            score += weight
    return min(score, 100.0)


def score_business_presence(lead: dict) -> float:
    """Assess digital footprint."""
    score = 0.0
    if lead.get("website"):
        score += 25
    if lead.get("email"):
        score += 20
    if lead.get("phone"):
        score += 20
    social = lead.get("social_links", [])
    if isinstance(social, str):
        social = json.loads(social) if social.startswith("[") else []
    score += min(len(social) * 10, 25)
    if lead.get("bbb_rating"):
        score += 10
    return min(score, 100.0)


def score_market_fit(lead: dict) -> float:
    """How well does this lead fit our target niches?"""
    niche = (lead.get("niche") or "").lower().strip()
    if niche in TARGET_NICHES:
        return 100.0
    # Partial match
    for target in TARGET_NICHES:
        if target in niche or niche in target:
            return 75.0
    # Check business_name for keywords
    name = (lead.get("business_name") or "").lower()
    roofing_keywords = {"roof", "shingle", "gutter", "siding", "storm", "restoration"}
    if any(kw in name for kw in roofing_keywords):
        return 80.0
    hvac_keywords = {"hvac", "heating", "cooling", "air", "furnace", "ac"}
    if any(kw in name for kw in hvac_keywords):
        return 80.0
    const_keywords = {"construction", "contractor", "build", "remodel", "reno"}
    if any(kw in name for kw in const_keywords):
        return 60.0
    return 30.0


def score_engagement_potential(lead: dict) -> float:
    """Use omega_score as proxy for engagement potential."""
    omega = float(lead.get("omega_score", 0) or 0)
    # Normalize to 0-100 (assuming omega is 0-1000 scale)
    return min(omega / 10, 100.0)


def score_enrichment_quality(lead: dict) -> float:
    """How many enrichment sources have returned data?"""
    return float(lead.get("enrichment_score", 0) or 0)


def compute_lead_score(lead: dict) -> dict:
    """Run all scoring dimensions and return composite."""
    dims = {
        "data_completeness": score_data_completeness(lead),
        "business_presence": score_business_presence(lead),
        "market_fit": score_market_fit(lead),
        "engagement_potential": score_engagement_potential(lead),
        "enrichment_quality": score_enrichment_quality(lead),
    }
    composite = sum(dims[k] * WEIGHTS[k] for k in dims)
    composite = round(min(composite, 100.0), 1)

    # Tier
    if composite >= 75:
        tier = "hot"
    elif composite >= 50:
        tier = "warm"
    elif composite >= 25:
        tier = "cold"
    else:
        tier = "dead"

    # Recommended action
    if tier == "hot":
        action = "Contact immediately — qualified lead"
    elif tier == "warm":
        action = "Add to nurture sequence, enrich further"
    elif tier == "cold":
        action = "Enrich more data before contacting"
    else:
        action = "Insufficient data — skip or archive"

    return {
        "composite_score": composite,
        "tier": tier,
        "dimensions": dims,
        "recommended_action": action,
    }


def get_qualification_summary(backend) -> dict:
    """Return qualification stats across all leads."""
    rows = backend.execute(
        "SELECT id, business_name, omega_score, enrichment_score, niche FROM crm_leads"
    ).fetchall()
    tiers = {"hot": 0, "warm": 0, "cold": 0, "dead": 0}
    niche_counts: dict = {}

    for r in rows:
        lead = dict(r)
        score_info = compute_lead_score(lead)
        tiers[score_info["tier"]] = tiers.get(score_info["tier"], 0) + 1
        n = lead.get("niche", "unknown") or "unknown"
        niche_counts[n] = niche_counts.get(n, 0) + 1

    return {
        "total_scored": len(rows),
        "tier_distribution": tiers,
        "top_niches": sorted(niche_counts.items(), key=lambda x: -x[1])[:10],
    }
