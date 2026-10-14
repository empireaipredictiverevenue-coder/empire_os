"""Attach first-party mailbox transport truth to a JEV review, without promotion."""
from __future__ import annotations

from typing import Any, Mapping
import re

from empire_os.jev_gtm_research_bridge import _request_identity
from empire_os.jev_gtm_mail_source_truth import SCHEMA


def attach_jev_ingress_release_gate(
    decision: Mapping[str, Any],
    observed: Mapping[str, Any],
) -> dict[str, Any]:
    _, _, _, decision_ref = _request_identity(decision)
    if not isinstance(observed, Mapping) or (
        observed.get("schema_version") != SCHEMA
        or observed.get("mode") != "OBSERVE"
        or observed.get("status") != "HOLD_FIRST_PARTY_REPLY_ACTIVATION"
        or observed.get("execution_authority") != "none"
        or observed.get("production_changes_performed") is not False
        or observed.get("mail_sent") is not False
        or observed.get("dns_modified") is not False
        or observed.get("mailbox_reads") is not False
        or observed.get("database_reads") is not False
        or observed.get("outbound_authorized") is not False
        or observed.get("first_party_inbound_transport_verified") is not False
        or observed.get("original_provider_receipt_identity_verified") is not False
        or observed.get("canonical_contact_verified") is not False
        or observed.get("independently_verified_buyer_replies") is not None
        or observed.get("verified_commercial_revenue") is not None
    ):
        raise ValueError("untrusted or privileged mailbox source truth")
    reasons = observed.get("blocked_reasons")
    if (not isinstance(reasons, list) or not reasons or len(reasons) > 30
            or any(not isinstance(v, str) or
                   not re.fullmatch(r"[A-Z0-9_]{3,100}", v) for v in reasons)):
        raise ValueError("canonical bounded inbox release blockers required")
    return {
        "schema_version": "empire.jev.ingress_release_gate_attachment.v1",
        "mode": "OBSERVE",
        "decision_fingerprint": decision_ref,
        "jev_action_unchanged": decision["action"],
        "mail_source_truth_status": "HOLD_FIRST_PARTY_REPLY_ACTIVATION",
        "mail_source_blockers": sorted(set(reasons)),
        "original_provider_reply_verified": False,
        "tenant_contact_verified": False,
        "suppression_clearance_verified": False,
        "buying_intent_verified": False,
        "realized_revenue": None,
        "revenue_eligible": False,
        "founder_review_required": True,
        "outbound_authorized": False,
        "database_write": False,
        "mailbox_write": False,
        "execution_authority": "none",
    }
