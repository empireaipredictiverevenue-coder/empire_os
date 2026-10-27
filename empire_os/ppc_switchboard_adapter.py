"""Canonical parked pay-per-call switchboard adapter.

This is the bridge between Empire Voice Lab and the future pay-per-call router.
It deliberately reuses current canonical buyer allocation truth rather than the
legacy in-memory bid table.

Until the switchboard canonical-refactor gate is explicitly activated, this
module is preview-only and cannot route calls, create payment requests, move
funds, or recognize revenue.
"""
from __future__ import annotations

from typing import Any, Mapping

from empire_os.buyer_allocation import plan_allocation
from empire_os.voice_routing_policy import switchboard_status
from empire_os.analytics.first_party_event_contract import (
    ALLOWED_CHANNELS, SCHEMA as ANALYTICS_EVENT_SCHEMA,
)
from empire_os.competitor_call_traffic_sources import FREE, PAID
from empire_os.conversion_intelligence import (
    HOMEOWNER_CALL_STAGES, review_homeowner_call_funnel,
)
from empire_os.call_unit_economics_review import (
    REQUIRED_FIELDS, REQUIRED_RECEIPTS, review_call_unit_economics,
)


def _buyer_index(
    buyers: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("id") or "").strip(): row
        for row in buyers
        if isinstance(row, dict)
        and str(row.get("id") or "").strip()
    }


def preview_pay_per_call_route(
    prospect: Mapping[str, Any],
    qualification: Mapping[str, Any] | None,
    identity_link: Mapping[str, Any] | None,
    buyers: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return a non-mutating canonical routing preview."""
    route_policy = switchboard_status()
    plan = plan_allocation(
        dict(prospect),
        dict(qualification) if isinstance(qualification, Mapping) else None,
        dict(identity_link) if isinstance(identity_link, Mapping) else None,
        buyers,
    )
    indexed = _buyer_index(buyers)

    candidates: list[dict[str, Any]] = []
    for candidate in plan.get("candidates") or []:
        buyer_id = str(candidate.get("buyer_id") or "").strip()
        source = indexed.get(buyer_id) or {}
        candidates.append({
            "buyer_id": buyer_id,
            "buyer_name": candidate.get("buyer_name"),
            "match_score": candidate.get("match_score"),
            "remaining_capacity": candidate.get("remaining_capacity"),
            "observed_rate": candidate.get("observed_rate"),
            "delivery_channel": (
                "phone"
                if str(source.get("destination_phone") or "").strip()
                else (
                    "webhook"
                    if str(source.get("webhook_url") or "").strip()
                    else None
                )
            ),
            "delivery_verified": bool(source.get("delivery_verified_at")),
            "capacity_verified": bool(source.get("capacity_verified_at")),
            "commercial_terms_verified": bool(
                source.get("commercial_terms_verified_at")
            ),
        })

    selected = candidates[0] if candidates else None
    underlying_decision = str(plan.get("decision") or "unknown")

    if route_policy["execution_allowed"] is not True:
        decision = "PARKED"
        reason = route_policy["reason"]
    elif underlying_decision != "ready":
        decision = "NO_ROUTE"
        reason = str(plan.get("reason") or underlying_decision)
    else:
        # Even after policy activation, this adapter remains preview-only
        # until a dedicated canonical execution RPC is implemented.
        decision = "REVIEW_ONLY_EXECUTOR_NOT_IMPLEMENTED"
        reason = "legacy_flags_cannot_activate_canonical_ppc_executor"

    return {
        "schema_version": "empire.ppc_switchboard_preview.v1",
        "decision": decision,
        "reason": reason,
        "route_policy": route_policy,
        "prospect_id": plan.get("prospect_id"),
        "niche_family": plan.get("niche_family"),
        "metro": plan.get("metro"),
        "allocation_key": plan.get("allocation_key"),
        "underlying_allocation_decision": underlying_decision,
        "selected_candidate": selected,
        "candidates": candidates,
        "current_pilot_stack_migration_preview": {
            "scope": "LEAD_SMART_US_ROOFING_ONLY",
            "existing_telephony_observer": "ringba",
            "existing_first_party_database": "EmpireDB PostgreSQL",
            "legacy_policy_transport": route_policy.get("canonical_transport"),
            "legacy_policy_database": route_policy.get("canonical_database"),
            "legacy_stack_can_be_reused_as_live_executor": False,
            "live_ringba_buyer_leg_verified": False,
            "buyer_human_answer_verified": False,
            "source_to_settlement_join_verified": False,
            "canonical_adapter_refactor_verified": False,
            "new_routing_service_created": False,
        },
        "owned_analytics_reuse": {
            "existing_event_contract": ANALYTICS_EVENT_SCHEMA,
            "existing_offline_channels": sorted(ALLOWED_CHANNELS),
            "future_source_families_for_owner_review": [
                "paid_search", "paid_social", "organic_video",
                "publisher_referral", "affiliate_partner", "phone_inbound",
                "consented_chat", "consented_email", "crm", "settlement",
            ],
            "event_ingestion_mode": "DORMANT_OFFLINE_SIMULATION_ONLY",
            "live_session_collection_verified": False,
            "website_consent_authority_verified": False,
            "buyer_call_attribution_verified": False,
            "realised_cash_join_verified": False,
            "channel_schema_extension_approved": False,
            "new_tracking_database_created": False,
        },
        "route_executed": False,
        "provider_call_created": False,
        "payment_action": False,
        "payment_rail": "usdt_bsc",
        "revenue_recognition": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }



def review_pay_per_call_source_to_cash(
    *,
    registry: Mapping[str, Any],
    source_id: str,
    cohort_ref: str,
    funnel_counts: dict[str, int | None] | None = None,
    funnel_evidence_refs: dict[str, str | None] | None = None,
    finance_values: dict[str, int | None] | None = None,
    finance_receipt_refs: dict[str, str | None] | None = None,
    source_lineage_verified: bool = False,
    buyer_source_approval_verified: bool = False,
    buyer_source_approval_ref: str | None = None,
    independent_finance_verified: bool = False,
    same_cohort_verified: bool = False,
) -> dict[str, Any]:
    """Unify ORIGINAL source registry, CRO and call economics. Never execute.

    Only original owner-backed aggregates may populate this pure evaluator.
    A syntactically valid evidence reference or claimed verification flag is
    not itself an independently authenticated commercial source. In particular
    buyer allocation is B2B prospect planning, NOT homeowner call routing.
    """
    if (not isinstance(registry, Mapping)
            or registry.get("schema_version") != "empire.call_traffic_source_registry.v1"
            or registry.get("mode") != "OBSERVE"
            or registry.get("source_count") != 15
            or registry.get("organic_earned_count") != 7
            or registry.get("paid_candidate_count") != 7
            or registry.get("policy_excluded_count") != 1
            or registry.get("media_spend_authorized") is not False
            or registry.get("outbound_authorized") is not False
            or registry.get("ad_account_mutation") is not False
            or registry.get("execution_authority") != "none"):
        raise ValueError("unverified original pay-per-call traffic registry")
    organic = registry.get("free_or_earned")
    paid = registry.get("paid_research_only")
    excluded = registry.get("excluded")
    if (not isinstance(organic, list) or len(organic) != 7
            or not isinstance(paid, list) or len(paid) != 7
            or not isinstance(excluded, list) or len(excluded) != 1):
        raise ValueError("source group contract not verified")
    rows = [*organic, *paid, *excluded]
    if (any(not isinstance(row, dict)
            or not isinstance(row.get("id"), str)
            or row.get("status") not in {
                "ORGANIC_EARNED_RESEARCH_ONLY",
                "PAID_UNFUNDED_RESEARCH_ONLY",
                "CONDITIONAL_ELIGIBILITY_REVIEW",
                "EXCLUDED_POLICY",
            }
            or row.get("eligible_for_immediate_ad_spend") is not False
            or row.get("buyer_campaign_traffic_source_accepted") is not False
            for row in rows)
            or len({row["id"] for row in rows}) != 15):
        raise ValueError("untrusted research source identity or permissions")
    if not isinstance(source_id, str) or source_id not in {r["id"] for r in rows}:
        raise ValueError("not an original approved research-source identifier")
    if (not isinstance(cohort_ref, str) or not 6 <= len(cohort_ref) <= 200
            or any(type(flag) is not bool for flag in (
                source_lineage_verified, buyer_source_approval_verified,
                independent_finance_verified, same_cohort_verified,
            ))):
        raise ValueError("invalid reviewed cohort or owner assertions")
    if buyer_source_approval_ref is not None and (
            not isinstance(buyer_source_approval_ref, str)
            or not 8 <= len(buyer_source_approval_ref) <= 240):
        raise ValueError("invalid buyer source approval reference")
    if buyer_source_approval_verified and not buyer_source_approval_ref:
        raise ValueError("buyer permission must cite the original owner")

    candidate = next(row for row in rows if row["id"] == source_id)
    excluded_by_policy = candidate.get("status") == "EXCLUDED_POLICY"
    if (candidate.get("cost_class") not in ({FREE} | PAID)
            or (candidate["cost_class"] == FREE) != (candidate in organic)
            or excluded_by_policy != (candidate in excluded)):
        raise ValueError("conflicting published source-policy classification")
    counts = funnel_counts if funnel_counts is not None else {
        stage: None for stage in HOMEOWNER_CALL_STAGES
    }
    refs = funnel_evidence_refs if funnel_evidence_refs is not None else {
        stage: None for stage in HOMEOWNER_CALL_STAGES
    }
    values = finance_values if finance_values is not None else {
        key: None for key in REQUIRED_FIELDS
    }
    cash_refs = finance_receipt_refs if finance_receipt_refs is not None else {
        key: None for key in REQUIRED_RECEIPTS
    }
    # Prevent two original owner stages from silently describing different
    # cohorts while appearing to be a common source-to-cash measurement.
    for shared in (
        "provider_connected_calls", "buyer_accepted_payable_calls",
        "independently_settled_calls",
    ):
        if counts.get(shared) is not None and values.get(shared) is not None:
            if counts[shared] != values[shared]:
                raise ValueError("CRO and cash observations disagree on cohort")
    valid_lineage = (
        source_lineage_verified and same_cohort_verified and not excluded_by_policy
    )
    cro = review_homeowner_call_funnel(
        source_id=source_id, cohort_ref=cohort_ref,
        counts=counts, evidence_refs=refs,
        source_lineage_verified=valid_lineage,
    )
    authorized_source_for_review = (
        buyer_source_approval_verified and bool(buyer_source_approval_ref)
        and not excluded_by_policy
    )
    unit = review_call_unit_economics(
        source_id=source_id, cohort_ref=cohort_ref, currency="USD",
        values=values, receipt_refs=cash_refs,
        source_attribution_verified=valid_lineage and authorized_source_for_review,
        independent_finance_verified=independent_finance_verified,
        same_cohort_verified=same_cohort_verified,
    )
    first_stage = cro["stage_reviews"][0]
    if excluded_by_policy:
        task = "DO_NOT_USE_POLICY_EXCLUDED_SOURCE"
        owner = "ORIGINAL_COMPLIANCE_AND_MEDIA_OWNER"
    elif first_stage["observed_count"] is None or not valid_lineage:
        task = "PROVE_FIRST_PARTY_SOURCE_AND_SESSION_COHORT"
        owner = "ORIGINAL_ANALYTICS_AND_WEBSITE_OWNER"
    elif not authorized_source_for_review:
        task = "VERIFY_BUYER_ALLOWED_TRAFFIC_SOURCE"
        owner = "ORIGINAL_BUYER_COMMERCIAL_OWNER"
    elif cro["measured_stage_count"] == 0:
        task = "RECONCILE_GENUINE_ZIP_TO_CALL_DISPOSITION"
        owner = "ORIGINAL_CRO_AND_CALL_QUALITY_OWNER"
    elif not unit["profitability_calibrated"]:
        task = "RECONCILE_ACCEPTED_SETTLED_CALLS_AND_ACTUAL_COSTS"
        owner = "ORIGINAL_FINANCE_AND_CALL_OWNER"
    else:
        task = "REVIEW_CRO_HYPOTHESIS_AGAINST_VERIFIED_CASH_MARGIN"
        owner = "ORIGINAL_CRO_AND_FOUNDER_OWNER"

    return {
        "schema_version": "empire.ppc.source_to_cash_switchboard_review.v1",
        "mode": "OBSERVE",
        "source_id": source_id, "cohort_ref": cohort_ref,
        "source_cost_class": candidate["cost_class"],
        "source_research_rank": candidate["research_rank"],
        "original_source_status": candidate["status"],
        "source_policy_excluded": excluded_by_policy,
        "source_research_reference_count": len(candidate.get("sources") or []),
        "buyer_source_approval_owner_asserted":
            buyer_source_approval_verified and bool(buyer_source_approval_ref),
        "original_owner_approval_document_authenticated_by_this_view": False,
        "existing_conversion_specialist_review": cro,
        "existing_per_call_economics_review": unit,
        "measured_funnel_stages": cro["measured_stage_count"],
        "reviewed_cash_margin_cents": unit["cash_margin_cents"],
        "profitability_reviewable_with_owner_assertions":
            unit["profitability_calibrated"],
        "next_task": task, "next_owner": owner,
        "competitor_research_is_not_verified_sales": True,
        "website_collection_enabled": False,
        "buyer_call_route_changed": False,
        "traffic_or_ad_spend_authorized": False,
        "automated_optimisation_enabled": False,
        "provider_call_created": False,
        "revenue_recognized": False,
        "new_agent_database_or_timer_created": False,
        "execution_authority": "none",
    }


def execute_pay_per_call_route(*_args: Any, **_kwargs: Any) -> None:
    """Hard stop until the canonical switchboard executor is implemented."""
    raise RuntimeError(
        "pay-per-call switchboard execution is parked; "
        "legacy Vonage/Supabase route retired, current Ringba/EmpireDB "
        "executor not implemented"
    )
