"""First-party JEV GTM bridge to existing canonical CRM channel evidence.

Calls the existing CRM reviewer; never interprets UNKNOWN as CLEAR and never
creates consent, sends mail or reads contact PII.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from empire_os.revenue_crm_channel_evidence import (
    TrustedChannelEvidence,
    review_channel_evidence,
)


def outreach_from_canonical_channel_evidence(
    prospect: Mapping[str, Any],
    *,
    evidence: TrustedChannelEvidence | None,
    as_of: datetime,
) -> dict[str, Any]:
    """Convert canonical email-channel review to *non-authorising* GTM facts."""
    reviewed = review_channel_evidence(
        prospect, channel="email", evidence=evidence, now=as_of,
    )
    blockers = set(reviewed["blockers"])
    suppressed = (
        reviewed["canonical_suppression_state"] == "suppressed"
        or "EXPLICIT_CHANNEL_OPT_OUT" in blockers
        or "CRM_CONTACT_HOLD" in blockers
    )
    preconditions = reviewed["consent_suppression_review_preconditions_met"] is True
    ref = evidence.suppression_evidence_ref if preconditions and evidence else None
    # Even a not_found suppression record never grants marketing send authority.
    return {
        "suppressed": suppressed,
        "do_not_contact": suppressed,
        "suppression_checked": preconditions,
        "suppression_state": (
            "SUPPRESSED" if reviewed["canonical_suppression_state"] == "suppressed"
            else "CLEAR" if preconditions else "UNKNOWN"
        ),
        "canonical_readback_verified": preconditions,
        "suppression_readback_ref": ref,
        "canonical_review_status": reviewed["review_status"],
        "canonical_review_schema_version": reviewed["schema_version"],
        "send_authorized": False,
        "execution_authority": "none",
    }
