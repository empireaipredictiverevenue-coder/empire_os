"""Read-only, cohort-separated handoff between Commercial Growth and existing BD desk.

Not a scheduler, task queue, CRM writer, buyer matcher or owner override.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

SCHEMA = "empire.commercial_growth_existing_owner_review.v1"
GROWTH_SCHEMA = "empire.commercial.video_growth_framework_review.v1"
BD_SCHEMA = "empire.bd.conversion_desk_review.v1"
ALLOWED_OWNERS = frozenset({
    "buyer_scout", "buyer_qualifier", "commercial_evidence_verifier",
    "decision_maker_resolver", "contact_verifier",
    "buyer_conversation_intake", "seat_readiness_agent",
})


def _bounded_count(value: Any) -> int | None:
    return value if type(value) is int and 0 <= value <= 1_000_000 else None


def _text(value: Any, length: int = 150) -> str:
    return " ".join(value.split())[:length] if isinstance(value, str) else ""


def review_existing_owner_handoff(
    *, commercial: Mapping[str, Any], buyer_development: Mapping[str, Any]
) -> dict[str, Any]:
    """Surface review priorities. Crucially does not join counts/IDs across cohorts."""
    if commercial.get("schema_version") != GROWTH_SCHEMA or commercial.get("mode") != "OBSERVE_ONLY":
        raise ValueError("exact isolated commercial review contract required")
    if commercial.get("database_writes") is not False or commercial.get("outbound_authority") != "NONE":
        raise ValueError("commercial review must have no execution authority")
    if buyer_development.get("schema_version") != BD_SCHEMA:
        raise ValueError("exact existing BD desk contract required")
    if buyer_development.get("mode") != "OBSERVE" or buyer_development.get("execution_authority") != "none":
        raise ValueError("existing BD desk must be non-executing")
    if buyer_development.get("outbound_allowed") is not False or buyer_development.get("database_writes") is not False:
        raise ValueError("existing BD desk must not claim external authority")

    freshness = commercial.get("source_freshness")
    gaps = commercial.get("readiness_gap_counts_nonexclusive")
    source_counts = commercial.get("source_counts")
    if not all(isinstance(x, Mapping) for x in (freshness, gaps, source_counts)):
        raise ValueError("commercial readiness and freshness required")
    has_stale = freshness.get("requires_refresh_before_commercial_use")
    if type(has_stale) is not bool:
        raise ValueError("commercial freshness decision required")

    bd_status = buyer_development.get("status")
    if bd_status not in ("BUSINESS_DEVELOPMENT_RESEARCH_TRIAGE_READY", "SOURCE_EVIDENCE_HOLD"):
        raise ValueError("unknown existing BD desk status")
    buyer_cohort_usable = bd_status == "BUSINESS_DEVELOPMENT_RESEARCH_TRIAGE_READY"
    activated = _bounded_count(buyer_development.get("fully_activated_buyer_count")) if buyer_cohort_usable else None
    bd_review_ready = _bounded_count(buyer_development.get("review_ready_count")) if buyer_cohort_usable else None
    bd_scout = _bounded_count(buyer_development.get("scout_candidate_count")) if buyer_cohort_usable else None
    historical_targets = _bounded_count(source_counts.get("canonical_offer_targets"))
    if historical_targets is None:
        raise ValueError("bounded historical offer target count required")
    for value in gaps.values():
        if _bounded_count(value) is None or value > historical_targets:
            raise ValueError("invalid overlapping gap count")

    review_steps = []
    if has_stale:
        review_steps.append({
            "existing_owner_lane": "commercial_source_owners",
            "review_action": "REFRESH_CANONICAL_OFFER_BOOK_AND_FUNNEL_AT_SOURCE",
            "reason": "commercial_snapshots_missing_or_stale",
        })
    if bd_status == "SOURCE_EVIDENCE_HOLD":
        review_steps.append({
            "existing_owner_lane": "buyer_acquisition_team",
            "review_action": "RESOLVE_EXISTING_BD_SOURCE_HOLD_WITH_OWNER",
            "reason": _text(buyer_development.get("hold_code"), 100) or "unknown",
        })
    elif activated == 0:
        review_steps.append({
            "existing_owner_lane": "commercial_evidence_verifier",
            "review_action": "VERIFY_REAL_BUYER_PURCHASE_TERMS_CAPACITY_AND_FULFILMENT",
            "reason": "zero_fully_activated_buyers_in_existing_bd_review",
        })
    if (gaps.get("CANONICAL_ID_MISSING") or 0) > 0:
        review_steps.append({
            "existing_owner_lane": "decision_maker_resolver",
            "review_action": "REVIEW_HISTORICAL_PROSPECT_ID_PROVENANCE_WITHOUT_FUZZY_JOIN",
            "reason": "historical_offer_rows_missing_canonical_ids",
        })
    if (gaps.get("PRODUCT_TERMS_OR_CATALOG_UNREADY") or 0) > 0:
        review_steps.append({
            "existing_owner_lane": "commercial_catalog_owner",
            "review_action": "VERIFY_ACTIVE_PRODUCTS_TERMS_AND_DELIVERABILITY",
            "reason": "historical_offer_rows_lack_verified_catalog_readiness",
        })
    if (gaps.get("EXISTING_CONVERSATION_REQUIRES_LIVE_THREAD_RECHECK") or 0) > 0:
        review_steps.append({
            "existing_owner_lane": "sales_director_operator",
            "review_action": "RECONCILE_EXISTING_THREADS_BEFORE_ANY_NEW_OUTREACH",
            "reason": "historical_offer_rows_contain_conversation_references",
        })

    # Preserve existing BD owner's recommendations without creating competing
    # jobs or making any new domain/person linkage. Counts are only from that
    # separate BD cohort. Unknown owner/action is omitted, not dispatched.
    source_actions = buyer_development.get("priority_actions") or []
    bd_owner_actions = []
    if buyer_cohort_usable and isinstance(source_actions, list):
        for action in source_actions[:30]:
            if not isinstance(action, Mapping):
                continue
            owner = _text(action.get("owner"), 64)
            description = _text(action.get("action"), 140)
            if owner not in ALLOWED_OWNERS or not description:
                continue
            bd_owner_actions.append({
                "owner_from_existing_bd_desk": owner,
                "existing_action": description,
                "reason": _text(action.get("reason"), 120),
                "reported_evidence_count": _bounded_count(action.get("evidence_count")),
                "task_created": False,
            })

    return {
        "schema_version": SCHEMA,
        "status": ("SOURCE_REVIEW_HOLD" if has_stale or not buyer_cohort_usable or activated is None or activated == 0 else "OWNER_REVIEW_ONLY"),
        "mode": "OBSERVE",
        "cohorts_are_separate_and_not_summable": True,
        "historical_offer_book_cohort": {
            "historical_offer_target_count": historical_targets,
            "fresh_for_commercial_use": not has_stale,
            "overlapping_gap_counts": dict(gaps),
        },
        "existing_buyer_development_cohort": {
            "desk_status": bd_status,
            "scout_candidate_count": bd_scout,
            "review_ready_count": bd_review_ready,
            "fully_activated_buyer_count": activated,
            "buyer_market_match_verified": buyer_development.get("buyer_market_match_verified") is True,
        },
        "existing_owner_review_suggestions": review_steps,
        "existing_bd_owner_priority_actions": bd_owner_actions,
        "buyer_identity_join_performed": False,
        "contact_access_performed": False,
        "outbound_allowed": False,
        "crm_mutations": False,
        "database_writes": False,
        "external_actions": False,
        "agent_tasks_created": False,
        "agent_owner_changes": False,
        "payment_authorized": False,
        "execution_authority": "none",
    }
