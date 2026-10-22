"""Draft-only bridge across the existing VC prospect and quote-buyer acquisition lanes.

Uses the canonical CopyBrief/CopyDraft, not a parallel copywriting engine.
The two lanes retain separate evidence namespaces; no buyer claims are inferred.
"""
from __future__ import annotations
from collections.abc import Mapping
from typing import Any

from empire_os.copywriter import CopyBrief

LANES = {"vc_portfolio", "contractor_quote"}
REQUIRED = ("company", "offer", "trigger", "trigger_ref", "offer_ref")


def prepare_acquisition_copy(*, lane: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    if lane not in LANES:
        raise ValueError("unknown acquisition lane")
    if not isinstance(evidence, Mapping):
        raise ValueError("evidence mapping required")
    missing = [k for k in REQUIRED if not isinstance(evidence.get(k), str)
               or not evidence[k].strip()]
    if missing:
        return {"status": "HOLD", "missing_evidence": missing, "send_allowed": False}
    if evidence.get("trigger_independently_verified") is not True or evidence.get("offer_approved") is not True:
        return {"status": "HOLD", "missing_evidence": [
            k for k in ("trigger_independently_verified", "offer_approved") if evidence.get(k) is not True
        ], "send_allowed": False}
    company = evidence["company"].strip()
    brief = CopyBrief(
        channel="cold_email",
        objective="Offer a scoped, relevant commercial example for review",
        product_code="acquisition_" + lane,
        product_name=evidence["offer"].strip(),
        audience="verified business decision maker",
        business_name=company,
        niche=lane,
        evidence={
            "why_now_summary": evidence["trigger"].strip(),
            "why_now_evidence_ref": evidence["trigger_ref"].strip(),
            "proof_summary": evidence.get("proof", ""),
            "proof_evidence_ref": evidence.get("proof_ref", ""),
        },
    )
    # Return a gated brief for the canonical copywriter, preserving source refs.
    # Canonical drafting/quality calls remain the owning pipeline's responsibility.
    return {
        "status": "READY_FOR_CANONICAL_COPY_REVIEW",
        "lane": lane,
        "brief": brief.as_dict(),
        "offer_ref": evidence["offer_ref"].strip(),
        "send_allowed": False,
        "suppression_checked": False,
        "recipient_permission_checked": False,
        "founder_approved": False,
        "crm_writes": False,
    }
