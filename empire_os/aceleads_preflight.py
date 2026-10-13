"""AceLeads UK commercial-roofing offline readiness check. No IO or delivery."""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

UK_POSTCODE = re.compile(r"^(GIR\s?0AA|(?:[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}))$", re.I)
REQUIRED = ("vertical", "property_type", "postcode", "work_required",
            "decision_maker_role", "source_url", "source_type",
            "consent_text_version", "privacy_notice_version",
            "consent_timestamp", "consent_source_url", "buyer_brief_id")


def preflight(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Inspect only. Never authorize real submission or mutate input."""
    blockers: list[str] = []
    for field in REQUIRED:
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            blockers.append(f"missing_{field}")
    if payload.get("vertical") != "commercial_roofing":
        blockers.append("unsupported_vertical")
    postcode = str(payload.get("postcode") or "").strip().upper()
    if not UK_POSTCODE.fullmatch(postcode):
        blockers.append("invalid_uk_postcode")
    if payload.get("synthetic") is not True:
        blockers.append("synthetic_only")
    if payload.get("mode") != "OBSERVE":
        blockers.append("observe_only")
    if payload.get("execution_authority") != "NONE":
        blockers.append("execution_forbidden")
    if payload.get("buyer_terms_approved") is not True:
        blockers.append("buyer_terms_unapproved")
    if payload.get("buyer_approved") is not True:
        blockers.append("buyer_not_approved")
    if payload.get("consent_verified") is not True:
        blockers.append("consent_not_verified")
    if payload.get("suppression_verified") is not True:
        blockers.append("suppression_not_verified")
    if payload.get("lead_delivery_authorized") is True:
        blockers.append("delivery_must_remain_disabled")
    return {
        "schema_version": "empire.aceleads.preflight.v1",
        "mode": "OBSERVE",
        "delivery_authorized": False,
        "review_ready": not blockers,
        "blockers": sorted(set(blockers)),
    }
