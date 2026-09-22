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
        decision = "READY_FOR_CANONICAL_EXECUTOR"
        reason = "canonical_route_preview_ready"

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
