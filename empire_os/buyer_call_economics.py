"""Buyer call economics and routing readiness.

Transforms verified buyer program inputs into deterministic pilot economics
without inventing payout, traffic cost, capacity, conversion rate or revenue.
"""

from __future__ import annotations

from typing import Any, Mapping


SCHEMA_VERSION = "empire.buyer_call_economics.v1"


def build_call_economics(
    *,
    buyer_name: str,
    program_ref: str,
    service: str,
    geography: str | None,
    payout_amount: float | None,
    payout_currency: str | None,
    qualification_seconds: int | None,
    daily_cap: int | None,
    traffic_source: str | None,
    traffic_source_approved: bool,
    routing_mode: str | None,
    routing_verified: bool,
    tracking_verified: bool,
    buyer_asset_approved: bool,
    estimated_cost_per_call: float | None = None,
) -> dict[str, Any]:
    buyer = str(buyer_name or "").strip()
    ref = str(program_ref or "").strip()
    svc = str(service or "").strip()

    if not buyer:
        raise ValueError("buyer_name is required")
    if not ref:
        raise ValueError("program_ref is required")
    if not svc:
        raise ValueError("service is required")

    blockers: list[str] = []

    if not geography:
        blockers.append("geography_unverified")
    if payout_amount is None or not payout_currency:
        blockers.append("payout_unverified")
    if qualification_seconds is None:
        blockers.append("qualification_rule_unverified")
    if daily_cap is None:
        blockers.append("capacity_unverified")
    if not traffic_source:
        blockers.append("traffic_source_unverified")
    if traffic_source_approved is not True:
        blockers.append("traffic_source_not_approved")
    if not routing_mode:
        blockers.append("routing_mode_unverified")
    if routing_verified is not True:
        blockers.append("routing_not_verified")
    if tracking_verified is not True:
        blockers.append("tracking_not_verified")
    if buyer_asset_approved is not True:
        blockers.append("buyer_asset_not_approved")

    margin = None
    if payout_amount is not None and estimated_cost_per_call is not None:
        margin = round(payout_amount - estimated_cost_per_call, 2)

    return {
        "schema_version": SCHEMA_VERSION,
        "buyer_name": buyer,
        "program_ref": ref,
        "service": svc,
        "geography": geography,
        "payout": {
            "amount": payout_amount,
            "currency": payout_currency,
            "verified": payout_amount is not None and bool(payout_currency),
        },
        "qualification": {
            "connected_call_seconds": qualification_seconds,
            "verified": qualification_seconds is not None,
        },
        "capacity": {
            "daily_cap": daily_cap,
            "verified": daily_cap is not None,
        },
        "acquisition": {
            "traffic_source": traffic_source,
            "buyer_approved": traffic_source_approved is True,
            "estimated_cost_per_call": estimated_cost_per_call,
        },
        "routing": {
            "mode": routing_mode,
            "verified": routing_verified is True,
        },
        "tracking": {
            "verified": tracking_verified is True,
        },
        "assets": {
            "buyer_approved": buyer_asset_approved is True,
        },
        "economics": {
            "gross_margin_per_accepted_call": margin,
            "margin_known": margin is not None,
        },
        "blockers": sorted(set(blockers)),
        "pilot_ready": not blockers,
        "live_traffic_authorized": False,
        "revenue_recognized": False,
    }


def routing_decision(economics: Mapping[str, Any]) -> dict[str, Any]:
    blockers = list(economics.get("blockers") or [])
    return {
        "decision": (
            "ready_for_separate_live_traffic_activation"
            if not blockers
            else "hold"
        ),
        "blockers": blockers,
        "live_traffic_authorized": False,
        "revenue_recognized": False,
    }
