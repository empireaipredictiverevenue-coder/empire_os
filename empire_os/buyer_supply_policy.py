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


def lead_smart_confirmed_roofing_policy(*, source_ref: str) -> dict[str, Any]:
    """Materialize Lead Smart roofing terms confirmed on 2026-10-05.

    Evidence is buyer-reported commercial policy only. This does not prove a
    live payout amount, tracking assignment, routing operation, fulfilment,
    revenue, or authorization to send traffic.
    """
    policy = build_buyer_supply_policy(
        buyer_name="Lead Smart",
        source_ref=source_ref,
        acquisition={
            "offer_name": "Main Roofing Contractors - Nationwide - Variable Rate",
            "service": "roofing",
            "preferred_work": [
                "installation",
                "replacement",
            ],
            "traffic_sources": {
                "organic_seo_landing_pages": {
                    "buyer_approved": True,
                },
                "paid_search": {
                    "creative_approved": True,
                    "brand_bidding_allowed": False,
                },
            },
            "buyer_approved": True,
            "traffic_source_approval_required": True,
        },
        creative={
            "unbranded_required": True,
            "generic_creative_required": True,
            "paid_search_copy_approved": True,
            "brand_bidding_allowed": False,
            "prohibited": [
                "promotions",
                "guarantees",
                "discounts",
                "unsubstantiated_claims",
            ],
        },
        conversion={
            "metric": "connected_call_seconds",
            "qualification_seconds": None,
            "qualification_seconds_min": 60,
            "qualification_seconds_max": 120,
            "qualification_route_dependent": True,
            "appointment_cpl_possible": True,
            "caller_requirement": "homeowner",
            "geography_requirement": "covered_zip",
            "duplicate_window_days": 30,
            "duplicate_pays_once": True,
            "scope": "most_buyers",
            "campaign_specific": True,
        },
        pricing={
            "dynamic": True,
            "pricing_mode": "live_bid_at_call_time",
            "coverage_tool_role": "planning",
            "mechanism_verified": True,
            "actual_payout_observed": False,
            "payout_value": None,
            "currency": None,
            "verified": False,
        },
        routing={
            "platform": "Ringba",
            "selected_mode": "direct",
            "available_modes": ["direct", "rtb"],
            "offer_application_required": True,

            # Ringba system evidence received 2026-10-06 confirms
            # Lead Smart approved Empire's roofing offer application.
            # This does not establish tracking or execution authority.
            "offer_application_status": "approved",
            "offer_application_approved": True,
            "ringba_offer_label": "Roofing - Nationwide",
            "ringba_campaign_id": "CA8278ed3f26e9495b881fe3833174d007",
            "payout_model": "VARIABLE_RATE",
            "payout_currency": "USD",
            "observed_payout_min": 5,
            "observed_payout_max": 150,
            "revshare_percentage": None,
            "rtb_enabled": False,
            # 2026-10-09: Seth reported everything *should* be active.
            # Buyer assertion is not equivalent to a connected-call proof.
            "buyer_route_report": {
                "status": "EXPECTED_ACTIVE_BUYER_REPORTED",
                "source_ref": "gmail:1a121bc6211d60b7",
                "observed_at": "2026-10-09T17:35:52Z",
                "independently_verified": False,
            },
            # Seth explicitly requires ZIP + exposed CID for RTB.
            # These are requirements, not evidence of an RTB integration.
            "rtb_transport_requirements": {
                "zipcode_required": True,
                "caller_id_required": True,
                "expose_caller_id": "yes",
                "caller_id_must_match_live_call": True,
                "transport_implemented": False,
            },
            "payout_value_authority": "RINGBA_REALISED_EVENT",
            "qualification_route_dependent": True,
            "appointment_cpl_possible": True,
            "max_tracking_numbers_without_prior_discussion": 5,
            "zip_coverage_required": True,
            "facebook_marketplace_allowed": False,
            "free_quote_claim_allowed": False,
            "free_estimate_claim_allowed": False,
            "fake_or_ai_generated_reviews_allowed": False,
            "required_site_disclaimer": (
                "This site is a free service to assist homeowners in connecting "
                "with local service contractors. All contractors are independent "
                "and this site does not warrant or guarantee any work performed. "
                "It is the responsibility of the homeowner to verify that the "
                "hired contractor furnishes the necessary license and insurance "
                "required for the work being performed. All persons depicted in "
                "a photo or video are actors or models and not contractors listed "
                "on this site."
            ),
            "offer_approval_source_ref": "gmail:1a1112c17349445a",
            "offer_approval_observed_at": "2026-10-06T12:24:24Z",

            "tracking_number_assigned": True,
            "tracking_number": "+18883579305",
            "tracking_verified": False,
            "routing_verified": False,
            "subids_required": False,
            "rtb_supported": True,
            "rtb_terms_verified": False,
            "reporting_fields": [
                "duration",
                "connect_status",
                "payout_per_call",
            ],
        },
        review={
            # Seth explicitly approved the unbranded paid-search copy.
            # Preserve site/landing-page review as unknown until evidence
            # specifically establishes those assets were reviewed.
            "sites_reviewed": False,
            "landing_pages_reviewed": False,
            "ads_reviewed": True,
        },
    )

    policy["capacity"] = {
        "mode": "uncapped",
        "daily_cap": None,
        "buyer_reported": True,
    }

    policy["operating_hours"] = {
        "timezone": "CST",
        "monday_friday": "08:00-18:00",
        "saturday_sunday": "10:00-16:00",
    }

    policy["evidence"] = {
        "observed_at": "2026-10-05T14:15:08Z",
        "evidence_type": "buyer_reported_email",
        "execution_authority": False,
    }

    return policy
