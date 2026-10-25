"""Read-only publisher evidence next-action decision for original buyer scout."""
from __future__ import annotations
from collections.abc import Mapping
from empire_os.buyer_mail_semantics import EVENT_CODES

PILOT = "PUBLISHER_ACCEPTED_OUTCOME_PILOT_REPORTED"
RATE = "PUBLISHER_REVENUE_SHARE_TARGET_REPORTED"
SIGNED = "PUBLISHER_SIGNED_TERMS_AND_COVERAGE_REQUIRED_REPORTED"

def publisher_next_evidence(row: Mapping[str, object]) -> dict:
    codes = row.get("last_reply_signals", [])
    if not isinstance(codes, list) or len(codes) > len(EVENT_CODES):
        raise ValueError("INVALID_PUBLISHER_REPLY_SIGNALS")
    if len(codes) != len(set(codes)) or any(c not in EVENT_CODES for c in codes):
        raise ValueError("UNTRUSTED_PUBLISHER_SIGNAL")
    if codes and (row.get("source") != "EXACT_TWO_WAY_DMARC_ALIGNED_EMAIL_REPORTED"
                  or row.get("outbound_authorized") is not False):
        raise ValueError("INVALID_PROVIDER_PROVENANCE")
    reported = PILOT in codes or RATE in codes
    return {
        "next_action": ("VERIFY_ONE_CONTRACTED_INSTALLER_BUYBOX_AND_PRICE"
                        if reported else "REVIEW_PUBLISHER_REPLY_NO_SEND"),
        "reported_pilot_interest": PILOT in codes,
        "reported_proposed_share": RATE in codes,
        "reported_signed_terms_gate": SIGNED in codes,
        "reported_evidence_ref": ("gmail:" + row["last_buyer_reply_id"]
                                  if reported and isinstance(row.get("last_buyer_reply_id"), str)
                                  else None),
        "required_evidence": [
            "one_signed_installer_agreement", "verified_MCS_and_service_postcodes",
            "buyer_acceptance_event_and_paid_price", "costs_and_publisher_margin",
            "settlement_disputes_attribution_and_consent",
        ] if reported else [],
        "quote_authorized": False, "traffic_authorized": False,
        "terms_verified": False, "buyer_capacity_verified": False,
        "outbound_authorized": False, "execution_authority": "NONE",
    }
