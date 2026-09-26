"""Review-only pilot assets for the recovered Lead Smart supply policy."""
from __future__ import annotations

import re
from typing import Any, Mapping

from empire_os.buyer_supply_policy import (
    build_buyer_supply_policy,
    lead_smart_observed_policy,
)

SCHEMA_VERSION = "empire.buyer_pilot_assets.v1"

PROHIBITED_PATTERNS: dict[str, tuple[str, ...]] = {
    "promotions": ("special offer", "limited time", "sale", "coupon"),
    "guarantees": ("guaranteed", "guarantee", "100% guaranteed"),
    "discounts": ("discount", "save ", "% off"),
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


def validate_asset_text(text: str) -> dict[str, Any]:
    value = str(text or "").strip()
    lowered = value.lower()
    violations: list[dict[str, str]] = []
    for category, patterns in PROHIBITED_PATTERNS.items():
        for pattern in patterns:
            if pattern.lower() in lowered:
                violations.append({"category": category, "pattern": pattern})
    return {
        "passed": not violations,
        "violations": violations,
        "text_present": bool(value),
    }


def _asset(asset_type: str, **fields: Any) -> dict[str, Any]:
    text_parts: list[str] = []
    for key in ("headline", "subheadline", "body", "cta", "description"):
        value = fields.get(key)
        if value:
            text_parts.append(str(value))
    for claim in fields.get("claims") or []:
        text_parts.append(str(claim))
    compliance = validate_asset_text("\n".join(text_parts))
    return {
        "asset_type": asset_type,
        "status": "REVIEW_ONLY",
        "brand": "generic_unbranded",
        **fields,
        "compliance": compliance,
    }


def build_lead_smart_pilot_assets(
    *,
    service_label: str,
    buyer_policy: Mapping[str, Any] | None = None,
    source_ref: str = "lead_smart_observed_requirements",
) -> dict[str, Any]:
    policy = build_buyer_supply_policy(
        observed_policy=buyer_policy or lead_smart_observed_policy()
    )

    service = str(service_label or "").strip() or "home services"

    landing = _asset(
        "landing_page",
        headline=f"Connect with a local {service} provider",
        subheadline=(
            f"Request help for {service} in your area and speak with an "
            "available service provider."
        ),
        body=(
            "Availability depends on service area and provider coverage. "
            "Call qualification and routing follow buyer-approved rules."
        ),
        cta="Call to check availability",
        claims=[],
    )
    search_ad = _asset(
        "search_ad",
        headline=f"Local {service} help",
        description=(
            f"Looking for {service}? Call to check local provider availability."
        ),
    )

    assets = [landing, search_ad]
    compliance_passed = all(
        bool(asset.get("compliance", {}).get("passed")) for asset in assets
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "buyer_name": "Lead Smart",
        "source_ref": source_ref,
        "service_label": service,
        "mode": "REVIEW_ONLY",
        "assets": assets,
        "compliance_passed": compliance_passed,
        "buyer_asset_review_required": True,
        "traffic_source_approval_required": True,
        "buyer_approved": False,
        "published": False,
        "campaign_created": False,
        "budget_authorized": False,
        "traffic_authorized": False,
        "commercial_activation_authorized": False,
        "current_supply_review": policy.get("readiness"),
    }
