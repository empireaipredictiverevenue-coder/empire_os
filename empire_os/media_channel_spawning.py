"""Evidence-gated channel spawning candidates for Empire Media OS."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from empire_os.media_os_foundation import (
    evaluate_channel_launch_candidate,
)


CHANNEL_DIMENSIONS = (
    "audience_demand",
    "content_supply_gap",
    "trend_velocity",
    "empire_expertise",
    "content_depth",
    "monetisation_potential",
    "buyer_density",
    "advertiser_value",
    "search_potential",
    "youtube_outliers",
    "product_alignment",
    "competitive_differentiation",
    "production_feasibility",
)


def build_channel_spawn_candidate(
    *,
    channel_concept: str,
    credible_ideas: Iterable[Mapping[str, Any]],
    evidence_refs: Iterable[str],
    dimension_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    ideas = [dict(row) for row in credible_ideas]
    refs = [str(x).strip() for x in evidence_refs if str(x).strip()]

    observed_dimensions = {
        key: dimension_evidence.get(key)
        for key in CHANNEL_DIMENSIONS
    }
    known_dimension_count = sum(
        value is not None
        for value in observed_dimensions.values()
    )

    content_depth_confirmed = len(ideas) >= 30
    market_evidence_confirmed = bool(
        refs
        and known_dimension_count >= 5
        and observed_dimensions.get("audience_demand") is not None
        and observed_dimensions.get("product_alignment") is not None
    )

    gate = evaluate_channel_launch_candidate(
        channel_concept=channel_concept,
        credible_idea_count=len(ideas),
        evidence_refs=refs,
        content_depth_confirmed=content_depth_confirmed,
        market_evidence_confirmed=market_evidence_confirmed,
    )

    return {
        "schema_version": "empire.media.channel_spawn_candidate.v1",
        "mode": "OBSERVE",
        "channel_concept": channel_concept,
        "credible_idea_count": len(ideas),
        "ideas": ideas,
        "dimension_evidence": observed_dimensions,
        "known_dimension_count": known_dimension_count,
        "evidence_refs": refs,
        "launch_gate": gate,
        "score": None,
        "ranking_owner": "quant_brain",
        "channel_created": False,
        "channel_launch_authorized": False,
        "execution_authority": gate["execution_authority"],
    }


def channel_portfolio_policy() -> dict[str, Any]:
    return {
        "schema_version": "empire.media.channel_portfolio_policy.v1",
        "flagship_channel": "EMPIRE AI",
        "flagship_first": True,
        "simultaneous_mass_channel_launch": False,
        "candidate_families": [
            "AI_REVENUE_SALES",
            "AI_CODING_BUILDERS",
            "AI_SEO_SEARCH_INTELLIGENCE",
            "AI_LEAD_GENERATION",
        ],
        "vertical_candidates": [
            "AI_FOR_ROOFING",
            "AI_FOR_PROPERTY",
            "AI_FOR_PRIVATE_CAPITAL",
            "AI_FOR_CONTRACTORS",
            "AI_FOR_ECOMMERCE",
            "AI_FOR_RECRUITMENT",
            "AI_FOR_WAREHOUSES",
            "STORM_DISASTER_OPPORTUNITY_INTELLIGENCE",
        ],
        "launch_requires_evidence": True,
        "minimum_credible_idea_count": 30,
        "preferred_credible_idea_range": [30, 50],
        "new_channel_launch_authorized": False,
        "execution_authority": "none",
    }
