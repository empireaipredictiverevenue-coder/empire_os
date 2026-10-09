"""Evidence-bound buyer supply review.

Turns buyer-stated supply requirements into deterministic readiness blockers.
This module never activates a buyer or authorizes live traffic.
"""

from __future__ import annotations

from typing import Any, Mapping

from empire_os.buyer_supply_policy import pilot_readiness


def build_supply_review(policy: Mapping[str, Any]) -> dict[str, Any]:
    buyer_name = str(policy.get("buyer_name") or "").strip()
    source_ref = str(policy.get("source_ref") or "").strip()

    if not buyer_name:
        raise ValueError("buyer_name is required")
    if not source_ref:
        raise ValueError("source_ref is required")

    acquisition = dict(policy.get("acquisition") or {})
    creative = dict(policy.get("creative") or {})
    pricing = dict(policy.get("pricing") or {})
    routing = dict(policy.get("routing") or {})

    asset_review = pilot_readiness(policy)
    blockers = list(asset_review["missing"])

    if (
        acquisition.get("traffic_source_approval_required") is True
        and acquisition.get("buyer_approved") is not True
    ):
        blockers.append("traffic_source_buyer_approval")

    if pricing.get("dynamic") is True:
        mechanism_verified = (
            pricing.get("mechanism_verified") is True
            or pricing.get("verified") is True
        )
        if not mechanism_verified:
            blockers.append("dynamic_payout_verification")

    selected_routing_mode = str(
        routing.get("selected_mode") or ""
    ).strip().lower() or None

    if selected_routing_mode == "direct":
        pass
    elif selected_routing_mode == "rtb":
        if routing.get("rtb_supported") is not True:
            blockers.append("rtb_not_supported")
        elif routing.get("rtb_terms_verified") is not True:
            blockers.append("rtb_terms_verification")
    elif selected_routing_mode is None:
        # Backward compatibility: historical policies did not distinguish
        # selected routing from available routing. Preserve their existing
        # fail-closed RTB requirement.
        if (
            routing.get("rtb_supported") is True
            and routing.get("rtb_terms_verified") is not True
        ):
            blockers.append("rtb_terms_verification")
    else:
        blockers.append("routing_mode_invalid")

    blockers = sorted(set(blockers))

    return {
        "schema_version": "empire.buyer_supply_review.v1",
        "buyer_name": buyer_name,
        "source_ref": source_ref,
        "policy_version": policy.get("policy_version"),
        "requirements": {
            "unbranded_required": creative.get("unbranded_required"),
            "generic_creative_required": creative.get(
                "generic_creative_required"
            ),
            "prohibited": list(creative.get("prohibited") or []),
            "traffic_source_approval_required": acquisition.get(
                "traffic_source_approval_required"
            ),
            "dynamic_pricing": pricing.get("dynamic"),
            "pricing_mechanism_verified": (
                pricing.get("mechanism_verified") is True
                or pricing.get("verified") is True
            ),
            "actual_payout_observed": (
                pricing.get("actual_payout_observed") is True
            ),
            "rtb_supported": routing.get("rtb_supported"),
            "selected_routing_mode": selected_routing_mode,
        },
        "asset_review": asset_review,
        "blockers": blockers,
        "pilot_ready": not blockers,
        "live_traffic_authorized": False,
        "commercial_activation_authorized": False,
    }
