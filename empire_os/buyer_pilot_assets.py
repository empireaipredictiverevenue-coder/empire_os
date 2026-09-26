"""Evidence-bound buyer pilot asset generation and compliance preflight.

Creates review-only acquisition assets from an observed buyer supply policy.
It does not publish, launch campaigns, authorize traffic, set budgets, or
invent geography, payout, capacity, demand or commercial terms.
"""

from __future__ import annotations

from typing import Any, Mapping

from empire_os.buyer_supply_review import build_supply_review


SCHEMA_VERSION = "empire.buyer_pilot_assets.v1"

PROHIBITED_PATTERNS = {
    "promotions": (
        "special offer",
        "limited time",
        "sale",
        "coupon",
    ),
    "guarantees": (
        "guaranteed",
        "guarantee",
        "100% guaranteed",
    ),
    "discounts": (
        "discount",
        "save ",
        "% off",
    ),
    "unsubstantiated_claims": (
        "best",
        "#1",
        "number one",
        "lowest price",
        "cheapest",
        "instant approval",
        "same-day guaranteed",
    ),
}


def validate_asset_text(
    text: str,
    *,
    prohibited_categories: list[str] | tuple[str, ...],
) -> dict[str, Any]:
    normalized = str(text or "").strip().lower()
    violations: list[dict[str, str]] = []

    for category in prohibited_categories:
        for pattern in PROHIBITED_PATTERNS.get(category, ()):
            if pattern.lower() in normalized:
                violations.append(
                    {
                        "category": category,
                        "pattern": pattern,
                    }
                )

    return {
        "compliant": not violations,
        "violations": violations,
    }


def build_lead_smart_pilot_assets(
    policy: Mapping[str, Any],
    *,
    service_label: str,
) -> dict[str, Any]:
    """Create review-only generic/unbranded pilot assets."""

    review = build_supply_review(policy)

    if str(policy.get("buyer_name") or "").strip() != "Lead Smart":
        raise ValueError("Lead Smart policy required")

    service = str(service_label or "").strip()
    if not service:
        raise ValueError("service_label required")

    creative = dict(policy.get("creative") or {})
    prohibited = list(creative.get("prohibited") or [])

    landing = {
        "asset_type": "landing_page",
        "status": "draft_for_buyer_review",
        "brand": None,
        "headline": f"Looking for help with {service}?",
        "subheadline": (
            "Tell us what service you need and where the property is located."
        ),
        "body": (
            "Submit your details to request contact regarding your service need. "
            "Availability and service coverage depend on location and provider capacity."
        ),
        "cta": "Request service information",
        "claims": [],
    }

    ads = [
        {
            "asset_type": "search_ad",
            "status": "draft_for_buyer_review",
            "brand": None,
            "headline": f"{service} Service Information",
            "description": (
                f"Looking for {service}? Submit your service request and location."
            ),
        },
        {
            "asset_type": "search_ad",
            "status": "draft_for_buyer_review",
            "brand": None,
            "headline": f"Need Help With {service}?",
            "description": (
                "Provide your location and service need to request more information."
            ),
        },
    ]

    checked_assets = []

    for asset in [landing, *ads]:
        text = " ".join(
            str(value)
            for value in asset.values()
            if isinstance(value, str)
        )

        validation = validate_asset_text(
            text,
            prohibited_categories=prohibited,
        )

        checked_assets.append(
            {
                **asset,
                "compliance": validation,
            }
        )

    compliant = all(
        asset["compliance"]["compliant"]
        for asset in checked_assets
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "buyer_name": "Lead Smart",
        "source_ref": policy.get("source_ref"),
        "service_label": service,
        "mode": "REVIEW_ONLY",
        "assets": checked_assets,
        "compliance_passed": compliant,
        "buyer_asset_review_required": True,
        "traffic_source_approval_required": True,
        "buyer_approved": False,
        "published": False,
        "campaign_created": False,
        "budget_authorized": False,
        "traffic_authorized": False,
        "commercial_activation_authorized": False,
        "current_supply_review": review,
    }
