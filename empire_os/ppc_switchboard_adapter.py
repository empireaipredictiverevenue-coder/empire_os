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


def execute_pay_per_call_route(*_args: Any, **_kwargs: Any) -> None:
    """Hard stop until the canonical switchboard executor is implemented."""
    raise RuntimeError(
        "pay-per-call switchboard execution is parked; "
        "canonical Vonage/Supabase/USDT-BSC executor not activated"
    )
