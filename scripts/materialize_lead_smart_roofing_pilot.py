#!/usr/bin/env python3
"""Materialize the Lead Smart roofing pilot review.

Evidence/materialization only.

This script:
- does not send messages
- does not apply to Ringba offers
- does not create tracking numbers
- does not enable routing
- does not authorize traffic
- does not recognize revenue
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from empire_os.buyer_pilot_assets import build_lead_smart_pilot_assets
from empire_os.buyer_supply_policy import lead_smart_confirmed_roofing_policy
from empire_os.buyer_supply_review import build_supply_review


SOURCE_REF = "gmail:1a10c6b2530f2951"
OUTPUT = Path("runtime/revenue/lead_smart/roofing_pilot_review.json")


def build_review() -> dict[str, Any]:
    policy = lead_smart_confirmed_roofing_policy(
        source_ref=SOURCE_REF,
    )

    supply_review = build_supply_review(policy)

    pilot_assets = build_lead_smart_pilot_assets(
        policy,
        service_label="Roofing",
    )

    pricing = dict(policy.get("pricing") or {})
    acquisition = dict(policy.get("acquisition") or {})
    conversion = dict(policy.get("conversion") or {})
    capacity = dict(policy.get("capacity") or {})
    routing = dict(policy.get("routing") or {})
    review = dict(policy.get("review") or {})

    commercial_truth = {
        "offer_name": acquisition.get("offer_name"),
        "service": acquisition.get("service"),
        "preferred_work": list(acquisition.get("preferred_work") or []),
        "organic_seo_approved": (
            acquisition
            .get("traffic_sources", {})
            .get("organic_seo_landing_pages", {})
            .get("buyer_approved")
            is True
        ),
        "paid_search_copy_approved": (
            policy.get("creative", {})
            .get("paid_search_copy_approved")
            is True
        ),
        "brand_bidding_allowed": (
            policy.get("creative", {})
            .get("brand_bidding_allowed")
        ),
        "qualification_seconds": conversion.get("qualification_seconds"),
        "qualification_seconds_min": policy["conversion"].get(
            "qualification_seconds_min"
        ),
        "qualification_seconds_max": policy["conversion"].get(
            "qualification_seconds_max"
        ),
        "qualification_route_dependent": policy["conversion"].get(
            "qualification_route_dependent"
        ),
        "appointment_cpl_possible": policy["conversion"].get(
            "appointment_cpl_possible"
        ),
        "caller_requirement": conversion.get("caller_requirement"),
        "geography_requirement": conversion.get("geography_requirement"),
        "duplicate_window_days": conversion.get("duplicate_window_days"),
        "duplicate_pays_once": conversion.get("duplicate_pays_once"),
        "capacity_mode": capacity.get("mode"),
        "daily_cap": capacity.get("daily_cap"),
        "pricing_mode": pricing.get("pricing_mode"),
        "payout": pricing.get("payout_value"),
        "currency": pricing.get("currency"),
        "payout_verified": pricing.get("verified") is True,
        "routing_platform": routing.get("platform"),
        "offer_application_status": routing.get("offer_application_status"),
        "offer_application_approved": (
            routing.get("offer_application_approved") is True
        ),
        "ringba_offer_label": routing.get("ringba_offer_label"),
        "ringba_campaign_id": routing.get("ringba_campaign_id"),
        "offer_approval_source_ref": routing.get(
            "offer_approval_source_ref"
        ),
        "offer_approval_observed_at": routing.get(
            "offer_approval_observed_at"
        ),
        "tracking_number_assigned": (
            routing.get("tracking_number_assigned") is True
        ),
        "tracking_number": routing.get("tracking_number"),
        "payout_model": routing.get("payout_model"),
        "payout_currency": routing.get("payout_currency"),
        "observed_payout_min": routing.get("observed_payout_min"),
        "observed_payout_max": routing.get("observed_payout_max"),
        "revshare_percentage": routing.get("revshare_percentage"),
        "rtb_enabled": routing.get("rtb_enabled"),
        "direct_route_requirements": dict(
            routing.get("direct_route_requirements") or {}
        ),
        "landing_review_report": dict(
            routing.get("landing_review_report") or {}
        ),
        "buyer_route_report": dict(routing.get("buyer_route_report") or {}),
        "rtb_transport_requirements": dict(
            routing.get("rtb_transport_requirements") or {}
        ),
        "payout_value_authority": routing.get("payout_value_authority"),
        "max_tracking_numbers_without_prior_discussion": routing.get(
            "max_tracking_numbers_without_prior_discussion"
        ),
        "zip_coverage_required": routing.get("zip_coverage_required"),
        "facebook_marketplace_allowed": routing.get(
            "facebook_marketplace_allowed"
        ),
        "free_quote_claim_allowed": routing.get("free_quote_claim_allowed"),
        "free_estimate_claim_allowed": routing.get(
            "free_estimate_claim_allowed"
        ),
        "fake_or_ai_generated_reviews_allowed": routing.get(
            "fake_or_ai_generated_reviews_allowed"
        ),
        "required_site_disclaimer": routing.get("required_site_disclaimer"),
        "tracking_verified": routing.get("tracking_verified") is True,
        "routing_verified": routing.get("routing_verified") is True,
        "subids_required": routing.get("subids_required"),
        "rtb_terms_verified": routing.get("rtb_terms_verified") is True,
        "ads_reviewed": review.get("ads_reviewed") is True,
        "sites_reviewed": review.get("sites_reviewed") is True,
        "landing_pages_reviewed": (
            review.get("landing_pages_reviewed") is True
        ),
        "operating_hours": dict(policy.get("operating_hours") or {}),
        "operating_hours_confirmation": dict(
            policy.get("operating_hours_confirmation") or {}
        ),
    }

    return {
        "buyer": "Lead Smart",
        "pilot": "roofing_pay_per_call",
        "status": (
            "READY_FOR_SEPARATE_ACTIVATION_REVIEW"
            if supply_review["pilot_ready"]
            else "REVIEW_ONLY"
        ),
        "source_ref": SOURCE_REF,
        "policy": policy,
        "commercial_truth": commercial_truth,
        "supply_review": supply_review,
        "pilot_assets": pilot_assets,

        # Hard authority boundary.
        # Application approval is evidence-bound independently from
        # tracking, routing and traffic execution authority.
        "ringba_offer_applied": True,
        "ringba_offer_approved": (
            routing.get("offer_application_approved") is True
        ),
        "tracking_bound": False,
        "routing_enabled": False,
        "traffic_enabled": False,
        "commercial_activation_authorized": False,
        "execution_authority": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write canonical runtime artifact.",
    )
    args = parser.parse_args()

    result = build_review()

    if args.write:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n"
        )
        print(f"wrote={OUTPUT}")

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
