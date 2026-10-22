"""Evidence-first buyer acquisition playbook for the existing Commercial Exchange.

Pure OBSERVE review. No discovery, persistence, CRM access, outbound or payment authority.
Only explicit owner-supplied evidence can advance a prospect's readiness.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

SCHEMA = "empire.buyer_acquisition_playbook.v1"

_REQUIRED = ("buyer_identity_verified", "commercial_need_evidenced",
             "offer_scope_documented", "contact_suppression_cleared",
             "contact_permission_cleared", "terms_accepted",
             "buyer_capacity_verified", "conversion_tracking_verified")


def review_buyer_offer(*, buyer_label: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Create a conservative, review-only buyer offer plan.

    Gate values must be literal True; missing, unknown and self-reported scores
    cannot silently authorize an offer or count revenue.
    """
    if not isinstance(buyer_label, str) or not buyer_label.strip():
        raise ValueError("buyer_label required")
    if not isinstance(evidence, Mapping):
        raise ValueError("evidence mapping required")
    if len(buyer_label) > 160:
        raise ValueError("buyer_label too long")
    verified = {gate: evidence.get(gate) is True for gate in _REQUIRED}
    missing = [gate for gate, passed in verified.items() if not passed]
    outreach_ready = all(verified[key] for key in (
        "buyer_identity_verified", "commercial_need_evidenced",
        "offer_scope_documented", "contact_suppression_cleared",
        "contact_permission_cleared"))
    pilot_ready = outreach_ready and all(verified[key] for key in (
        "terms_accepted", "buyer_capacity_verified",
        "conversion_tracking_verified"))
    # Settlement can only be asserted from the canonical outcome owner, not this adapter.
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "buyer_label": buyer_label.strip(),
        "evidence_gates": verified,
        "missing_evidence": missing,
        "outreach_review_status": "ELIGIBLE_FOR_HUMAN_REVIEW" if outreach_ready else "HOLD",
        "pilot_review_status": "ELIGIBLE_FOR_HUMAN_REVIEW" if pilot_ready else "HOLD",
        "offer_outline": {
            "problem": "Document the buyer's evidenced acquisition problem",
            "solution": "Match consented, qualified demand to buyer-approved scope",
            "proof": "Use independently verifiable delivery and acceptance receipts",
            "commercial_terms": "Require written scope, pricing, returns and settlement rules",
        },
        "next_action": ("Request explicit founder review; do not send automatically"
                        if outreach_ready else
                        "Obtain missing independent evidence before proposing outreach"),
        "outbound_authorized": False,
        "pilot_activated": False,
        "crm_writes": False,
        "payment_execution": False,
        "revenue_verified": False,
        "realised_revenue": None,
    }
