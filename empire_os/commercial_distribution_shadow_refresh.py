"""Evidence-only preview of the EXISTING Revenue Distribution pure projection.

Never calls refresh_revenue_distribution. Never writes runtime snapshots.
The current calculation clock is not a source-evidence observation timestamp.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from empire_os.revenue_distribution import (
    SOURCES, build_revenue_distribution,
)

SCHEMA = "empire.commercial.shadow_distribution_refresh_review.v1"
PREVIOUS_SCHEMA = "empire.revenue_distribution.v1"
KNOWN_SOURCE_STATES = frozenset({
    "available", "missing_or_invalid", "unknown_freshness", "future_dated",
    "stale", "producer_unavailable",
})
SOURCE_OWNERS = {
    "conversion": "conversion_intelligence_owner",
    "catalog": "commercial_catalog_owner",
    "radar": "opportunity_radar_owner",
    "buyer_acquisition": "buyer_acquisition_team",
    "buyer_scout": "buyer_scout",
    "buyer_capacity": "commercial_evidence_verifier",
    "exchange": "commercial_exchange_owner",
    "search": "agent_web_search_owner",
    "aeo": "aeo_intelligence_owner",
    "competitor": "competitor_search_intelligence_owner",
    "crawler": "acquisition_source_owner",
}


def shadow_distribution_refresh_review(
    *,
    source_snapshots: Mapping[str, Any],
    previous_distribution: Mapping[str, Any],
    now: datetime,
) -> dict[str, Any]:
    """Review upstream provenance and a shadow distribution calculation.

    No source content, company, email, prospect, or opportunity list escapes.
    """
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("trusted timezone-aware clock required")
    if not isinstance(source_snapshots, Mapping) or set(source_snapshots) != set(SOURCES):
        raise ValueError("exact existing Revenue Distribution source contract required")
    if previous_distribution.get("schema_version") != PREVIOUS_SCHEMA:
        raise ValueError("prior canonical Revenue Distribution contract required")
    if previous_distribution.get("execution_authority") != "none":
        raise ValueError("prior distribution must be non-executing")
    prior_opportunities = previous_distribution.get("opportunities")
    if not isinstance(prior_opportunities, list) or len(prior_opportunities) > 5000:
        raise ValueError("bounded prior opportunity array required")

    # Existing owner function is pure. Never invoke refresh_revenue_distribution.
    projected = build_revenue_distribution(
        source_snapshots,
        generated_at=now.astimezone(timezone.utc).isoformat(),
        acquisition_budget_cents=None,
    )
    if projected.get("schema_version") != PREVIOUS_SCHEMA:
        raise ValueError("owner projection contract changed")
    if (
        projected.get("execution_authority") != "none"
        or projected.get("proposal_only") is not True
        or not isinstance(projected.get("sources"), Mapping)
        or set(projected["sources"]) != set(SOURCES)
        or not isinstance(projected.get("authority"), Mapping)
        or any(value is not False for value in projected["authority"].values())
    ):
        raise ValueError("owner projection not independently proven non-executing")

    statuses: dict[str, str] = {}
    holds = []
    for name in SOURCES:
        status = projected["sources"][name].get("status")
        if status not in KNOWN_SOURCE_STATES:
            raise ValueError("unknown owner source status")
        statuses[name] = status
        if status != "available":
            holds.append({
                "existing_owner_lane": SOURCE_OWNERS[name],
                "source": name,
                "source_state": status,
                "review_action": "REVIEW_ORIGINAL_PRODUCER_FRESHNESS_AND_PROVENANCE",
                "manual_owner_review_only": True,
                "refresh_executed": False,
            })
    actions = projected.get("distribution_actions")
    opportunities = projected.get("opportunities")
    if (
        not isinstance(opportunities, list) or len(opportunities) > 5000
        or not isinstance(actions, list) or len(actions) > 5000
    ):
        raise ValueError("bounded owner distribution projection required")
    capacity = projected.get("buyer_capacity")
    if not isinstance(capacity, Mapping):
        raise ValueError("owner buyer capacity source projection required")
    capacity_view = {
        key: capacity.get(key) if type(capacity.get(key)) is int and 0 <= capacity.get(key) <= 1_000_000 else None
        for key in ("buyers_seen", "fully_activated", "terms_verified", "capacity_verified")
    }
    # Never turn research opportunity, available product or assumed potential
    # buyer into confirmed demand, payments, profit or buyer activation.
    owner_status = "SOURCE_FRESHNESS_HOLD" if holds else "DISTRIBUTION_SHADOW_REVIEW_ONLY"
    if capacity_view["fully_activated"] in (None, 0):
        owner_status = "SOURCE_AND_BUYER_EVIDENCE_HOLD" if holds else "BUYER_EVIDENCE_HOLD"
    return {
        "schema_version": SCHEMA,
        "status": owner_status,
        "mode": "OBSERVE",
        "shadow_generated_at": now.astimezone(timezone.utc).isoformat(),
        "no_current_revenue_or_buyer_evidence_inferred": True,
        "owner_distribution_producer_not_invoked": True,
        "canonical_distribution_snapshot_untouched": True,
        "source_count": len(statuses),
        "source_states": statuses,
        "source_state_counts": dict(sorted(Counter(statuses.values()).items())),
        "source_owner_review_holds": holds,
        "previous_stored_research_opportunity_count": len(prior_opportunities),
        "shadow_research_opportunity_count": len(opportunities),
        "difference_is_not_verified_new_business": True,
        "shadow_proposed_action_count_not_executed": len(actions),
        "buyer_capacity_source_counts_not_buyer_demand_proof": capacity_view,
        "source_evidence_review_required": bool(holds),
        "buyer_capacity_verification_required": capacity_view["fully_activated"] in (None, 0),
        "payment_authorized": False,
        "live_outbound_authorized": False,
        "paid_ad_spend_authorized": False,
        "auto_publication": False,
        "model_training": False,
        "agent_tasks_created": False,
        "crm_mutations": False,
        "database_writes": False,
        "snapshot_writes": False,
        "execution_authority": "none",
    }
