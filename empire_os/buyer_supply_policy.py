"""Evidence-bound buyer supply policy.

Represents buyer-stated acquisition, creative, conversion and routing
requirements without inventing commercial terms, coverage, capacity or price.

A policy may describe a buyer before that buyer is eligible for allocation.
Missing evidence remains unknown and activation remains fail-closed.
"""

from __future__ import annotations

from typing import Any, Mapping


POLICY_VERSION = "buyer_supply_policy_v1"


def _bool(value: Any) -> bool:
    return value is True


def build_buyer_supply_policy(
    *,
    buyer_name: str,
    source_ref: str,
    acquisition: Mapping[str, Any] | None = None,
    creative: Mapping[str, Any] | None = None,
    conversion: Mapping[str, Any] | None = None,
    pricing: Mapping[str, Any] | None = None,
    routing: Mapping[str, Any] | None = None,
    review: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an evidence-bound buyer policy.

    This function does not activate a buyer, infer payouts, infer geography,
    infer capacity, accept terms, or authorize live traffic.
    """
    name = str(buyer_name or "").strip()
    evidence_ref = str(source_ref or "").strip()

    if not name:
        raise ValueError("buyer_name is required")
    if not evidence_ref:
        raise ValueError("source_ref is required")

    acquisition = dict(acquisition or {})
    creative = dict(creative or {})
    conversion = dict(conversion or {})
    pricing = dict(pricing or {})
    routing = dict(routing or {})
    review = dict(review or {})

    return {
        "policy_version": POLICY_VERSION,
        "buyer_name": name,
        "source_ref": evidence_ref,
        "acquisition": acquisition,
        "creative": creative,
        "conversion": conversion,
        "pricing": pricing,
        "routing": routing,
        "review": review,
    }


def pilot_readiness(policy: Mapping[str, Any]) -> dict[str, Any]:
    """Return deterministic readiness without granting activation authority."""
    review = dict(policy.get("review") or {})

    required = (
        "sites_reviewed",
        "landing_pages_reviewed",
        "ads_reviewed",
    )

    missing = [
        field
        for field in required
        if not _bool(review.get(field))
    ]

    ready = not missing

    return {
        "ready": ready,
        "decision": (
            "ready_for_separate_activation_review"
            if ready
            else "blocked_pending_buyer_asset_review"
        ),
        "missing": missing,
        "live_traffic_authorized": False,
    }


def lead_smart_observed_policy(*, source_ref: str) -> dict[str, Any]:
    """Materialize only the requirements explicitly stated by Lead Smart.

    Dynamic payout values, live geographies, service demand, capacity and
    volume remain unknown until separately observed and verified.
    """
    return build_buyer_supply_policy(
        buyer_name="Lead Smart",
        source_ref=source_ref,
        acquisition={
            "proposed_source": "empire_first_party_search_led",
            "buyer_approved": False,
            "traffic_source_approval_required": True,
        },
        creative={
            "unbranded_required": True,
            "generic_creative_required": True,
            "prohibited": [
                "promotions",
                "guarantees",
                "discounts",
                "unsubstantiated_claims",
            ],
        },
        conversion={
            "metric": "connected_call_seconds",
            "typical_min_seconds": 90,
            "typical_max_seconds": 120,
            "campaign_max_seconds_observed": 150,
            "campaign_specific": True,
        },
        pricing={
            "dynamic": True,
            "update_frequency_observed": "daily",
            "payout_value": None,
            "currency": None,
            "verified": False,
        },
        routing={
            "rtb_supported": True,
            "rtb_terms_verified": False,
        },
        review={
            "sites_reviewed": False,
            "landing_pages_reviewed": False,
            "ads_reviewed": False,
        },
    )
