"""Attach original Search Fabric SERP evidence to previously derived keyword ideas.

Never call a new search API or turn a SERP position into keyword volume,
organic keyword difficulty, paid intent, conversions, or revenue.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from empire_os.public_intent_offer_method_bridge import SCHEMA
from empire_os.search_intelligence.serp import SerpSnapshot
from empire_os.search_intelligence.competitor_gap import analyse_competitor_gap


def review_existing_serp_snapshot(
    research: Mapping[str, Any],
    snapshot: SerpSnapshot,
    *,
    empire_domains: tuple[str, ...] = ("empire-ai.co.uk",),
    now: datetime | None = None,
    max_age_days: int = 7,
) -> dict[str, Any]:
    if research.get("schema_version") != SCHEMA:
        raise ValueError("original_keyword_bridge_review_required")
    if not isinstance(snapshot, SerpSnapshot):
        raise ValueError("original_serp_snapshot_required")
    clean = " ".join(snapshot.query.strip().lower().split())
    ideas = {p["keyword"] for p in research.get("keyword_candidates", [])}
    if clean not in ideas:
        raise ValueError("serp_query_not_in_original_keyword_research")
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("timezone_aware_now_required")
    try:
        observed = datetime.fromisoformat(snapshot.observed_at)
    except (ValueError, TypeError):
        raise ValueError("serp_observation_timestamp_unusable") from None
    if observed.tzinfo is None or observed > instant or instant - observed > timedelta(days=max_age_days):
        raise ValueError("serp_observation_old_future_or_naive")
    if (not snapshot.engine or snapshot.engine == "none"
            or not snapshot.quality_gate or snapshot.cache is None):
        raise ValueError("serp_provenance_insufficient")
    gap = analyse_competitor_gap(snapshot, empire_domains=empire_domains)
    return {
        "schema_version": "empire.search.public_intent_serp_review.v1",
        "mode": "OBSERVE",
        "owner": "empire_os.search_intelligence.competitor_gap",
        "keyword_idea": clean,
        "observed_at": snapshot.observed_at,
        "engine": snapshot.engine,
        "search_fabric_quality_gate": snapshot.quality_gate,
        "cache": snapshot.cache,
        "available": gap.available,
        "serp_evidence": gap.as_dict(),
        "query_search_volume": None,
        "cpc": None,
        "organic_keyword_difficulty": None,
        "estimated_traffic": None,
        "offer_payout": None,
        "predicted_profit": None,
        "realised_revenue": None,
        "launch_recommendation": "HUMAN_REVIEW_RESEARCH_ONLY" if gap.available else "HOLD_NO_SERP_EVIDENCE",
        "publishing_authorized": False,
        "indexation_authorized": False,
        "outbound_authorized": False,
        "database_writes": False,
        "execution_authority": "none",
    }
