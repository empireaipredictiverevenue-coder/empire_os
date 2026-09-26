"""Evidence-bound buyer supply policy for Lead Smart.

Recovered from the prior Lead Smart pilot work. This module is deliberately
fail-closed: observed buyer requirements may be represented, but unknown
commercial terms remain unknown and no traffic/send authority is granted.
"""
from __future__ import annotations

from typing import Any, Mapping

POLICY_VERSION = "buyer_supply_policy_v1"


def _bool(value: Any) -> bool:
    return value is True


def lead_smart_observed_policy() -> dict[str, Any]:
    return {
        "policy_version": POLICY_VERSION,
        "buyer_name": "Lead Smart",
        "source_ref": "lead_smart_observed_requirements",
        "proposed_source": "empire_first_party_search_led",
        "buyer_approved": False,
        "creative_requirements": {
            "brand_mode": "generic_unbranded",
            "unbranded_required": True,
            "generic_required": True,
            "prohibited": [
                "promotions",
                "guarantees",
                "discounts",
                "unsubstantiated_claims",
            ],
        },
        "call_requirements": {
            "connected_duration_seconds_typical_min": 90,
            "connected_duration_seconds_typical_max": 120,
            "campaign_max_observed_seconds": 150,
            "real_homeowner_required": True,
            "service_area_match_required": True,
        },
        "pricing": {
            "model": "dynamic_daily",
            "payout_value": None,
            "currency": None,
            "verified": False,
        },
        "rtb": {
            "supported": True,
            "terms_verified": False,
        },
        "commercial": {
            "geographies": None,
            "trades": None,
            "daily_cap": None,
            "capacity_verified": False,
            "delivery_destination_verified": False,
        },
        "review": {
            "traffic_source_approved": False,
            "landing_page_approved": False,
            "ad_creative_approved": False,
            "buyer_asset_review_complete": False,
            "commercial_terms_verified": False,
        },
        "traffic_authorized": False,
        "commercial_activation_authorized": False,
    }


def build_buyer_supply_policy(
    buyer: Mapping[str, Any] | None = None,
    *,
    observed_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    base = dict(observed_policy or lead_smart_observed_policy())
    buyer_row = dict(buyer or {})

    review = dict(base.get("review") or {})
    commercial = dict(base.get("commercial") or {})
    pricing = dict(base.get("pricing") or {})
    rtb = dict(base.get("rtb") or {})

    # Only promote explicit verified values supplied by canonical buyer data.
    if buyer_row.get("traffic_source_approved") is True:
        review["traffic_source_approved"] = True
    if buyer_row.get("landing_page_approved") is True:
        review["landing_page_approved"] = True
    if buyer_row.get("ad_creative_approved") is True:
        review["ad_creative_approved"] = True
    if buyer_row.get("buyer_asset_review_complete") is True:
        review["buyer_asset_review_complete"] = True
    if buyer_row.get("commercial_terms_verified") is True:
        review["commercial_terms_verified"] = True

    if buyer_row.get("payout_value") not in (None, ""):
        pricing["payout_value"] = buyer_row.get("payout_value")
    if buyer_row.get("currency") not in (None, ""):
        pricing["currency"] = buyer_row.get("currency")
    pricing["verified"] = _bool(buyer_row.get("pricing_verified"))

    if buyer_row.get("geographies") not in (None, ""):
        commercial["geographies"] = buyer_row.get("geographies")
    if buyer_row.get("trades") not in (None, ""):
        commercial["trades"] = buyer_row.get("trades")
    if buyer_row.get("daily_cap") not in (None, ""):
        commercial["daily_cap"] = buyer_row.get("daily_cap")
    commercial["capacity_verified"] = _bool(buyer_row.get("capacity_verified"))
    commercial["delivery_destination_verified"] = _bool(
        buyer_row.get("delivery_destination_verified")
    )

    if buyer_row.get("rtb_terms_verified") is True:
        rtb["terms_verified"] = True

    result = {
        **base,
        "review": review,
        "commercial": commercial,
        "pricing": pricing,
        "rtb": rtb,
        "buyer_approved": _bool(buyer_row.get("buyer_approved")),
    }
    readiness = pilot_readiness(result)
    result["readiness"] = readiness
    result["traffic_authorized"] = readiness["traffic_authorized"]
    result["commercial_activation_authorized"] = readiness[
        "commercial_activation_authorized"
    ]
    return result


def pilot_readiness(policy: Mapping[str, Any]) -> dict[str, Any]:
    review = dict(policy.get("review") or {})
    commercial = dict(policy.get("commercial") or {})
    pricing = dict(policy.get("pricing") or {})
    rtb = dict(policy.get("rtb") or {})

    blockers: list[str] = []
    if not _bool(policy.get("buyer_approved")):
        blockers.append("buyer_approval_missing")
    if not _bool(review.get("traffic_source_approved")):
        blockers.append("traffic_source_approval_missing")
    if not _bool(review.get("landing_page_approved")):
        blockers.append("landing_page_approval_missing")
    if not _bool(review.get("ad_creative_approved")):
        blockers.append("ad_creative_approval_missing")
    if not _bool(review.get("buyer_asset_review_complete")):
        blockers.append("buyer_asset_review_incomplete")
    if not _bool(review.get("commercial_terms_verified")):
        blockers.append("commercial_terms_unverified")
    if not _bool(pricing.get("verified")):
        blockers.append("pricing_unverified")
    if pricing.get("payout_value") in (None, ""):
        blockers.append("payout_unknown")
    if pricing.get("currency") in (None, ""):
        blockers.append("currency_unknown")
    if commercial.get("geographies") in (None, ""):
        blockers.append("geographies_unknown")
    if commercial.get("trades") in (None, ""):
        blockers.append("trades_unknown")
    if commercial.get("daily_cap") in (None, ""):
        blockers.append("daily_cap_unknown")
    if not _bool(commercial.get("capacity_verified")):
        blockers.append("capacity_unverified")
    if not _bool(commercial.get("delivery_destination_verified")):
        blockers.append("delivery_destination_unverified")
    if _bool(rtb.get("supported")) and not _bool(rtb.get("terms_verified")):
        blockers.append("rtb_terms_unverified")

    ready = not blockers
    return {
        "decision": (
            "ready_for_controlled_pilot"
            if ready
            else "blocked_pending_buyer_asset_review"
        ),
        "blockers": blockers,
        "traffic_authorized": ready,
        "commercial_activation_authorized": ready,
    }
