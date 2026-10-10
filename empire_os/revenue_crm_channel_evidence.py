"""Fail-closed, no-PII channel evidence review for existing Revenue CRM.

The canonical Revenue CRM view intentionally does not expose contact identities,
marketing opt-ins or outbound suppression rows. Therefore UNKNOWN is the default,
and even fully evidenced contact review NEVER grants marketing send authority.
Evidence must arrive from a separately authenticated *server-side* reader only.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Mapping
from uuid import UUID

from empire_os.revenue_crm_journeys import CHANNELS, STATUS_EXCLUDE

SCHEMA = "empire.crm_channel_evidence_review.v1"
VERIFIED_SOURCE = "empiredb_canonical_channel_evidence_reader"
MAX_EVIDENCE_AGE = timedelta(hours=24)

class ChannelEvidenceError(ValueError):
    """Wrong tenant, prospect, channel or untrusted evidence source."""

def canonical_uuid(value: Any) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        raise ChannelEvidenceError("canonical identity required") from None

@dataclass(frozen=True)
class TrustedChannelEvidence:
    """Opaque proof only; never an email, phone, cookie or marketing token."""
    tenant_id: str
    prospect_id: str
    channel: str
    identity_bound: bool
    consent_state: str             # verified_opt_in | opted_out | unknown
    suppression_state: str         # suppressed | not_found | unknown
    consent_evidence_ref: str | None
    suppression_evidence_ref: str | None
    observed_at: datetime
    source: str = VERIFIED_SOURCE

def review_channel_evidence(
    prospect: Mapping[str, Any], *, channel: str,
    evidence: TrustedChannelEvidence | None,
    now: datetime,
) -> dict[str, Any]:
    """Return BLOCKED, HOLD or REVIEW_ONLY; never an executable allow decision."""
    if now.tzinfo is None:
        raise ChannelEvidenceError("timezone-aware UTC clock required")
    if not isinstance(prospect, Mapping):
        raise ChannelEvidenceError("canonical CRM prospect mapping required")
    tenant = canonical_uuid(prospect.get("tenant_id"))
    pid = canonical_uuid(prospect.get("prospect_id"))
    if channel not in CHANNELS:
        raise ChannelEvidenceError("unsupported channel")
    blockers = ["SENDER_PROVIDER_NOT_VERIFIED", "FOUNDER_OUTBOUND_AUTHORITY_REQUIRED"]
    contact_status = str(prospect.get("prospect_status") or "").strip().casefold()
    direct_hold = contact_status in STATUS_EXCLUDE

    # Only a separately bound read transport can construct trusted evidence.
    # Unknown does not mean suppression clearance, even if a table lookup
    # eventually returns zero rows: identity and scoped consent must also pass.
    consent = "unknown"
    suppression = "unknown"
    valid_identity = False
    evidence_recent = False
    if evidence is not None:
        if not isinstance(evidence, TrustedChannelEvidence):
            raise ChannelEvidenceError("typed server evidence required")
        if (canonical_uuid(evidence.tenant_id) != tenant
                or canonical_uuid(evidence.prospect_id) != pid
                or evidence.channel != channel
                or evidence.source != VERIFIED_SOURCE):
            raise ChannelEvidenceError("untrusted or cross-tenant channel evidence")
        if (type(evidence.identity_bound) is not bool
                or evidence.consent_state not in ("verified_opt_in", "opted_out", "unknown")
                or evidence.suppression_state not in ("suppressed", "not_found", "unknown")
                or not isinstance(evidence.observed_at, datetime)
                or evidence.observed_at.tzinfo is None):
            raise ChannelEvidenceError("malformed channel evidence")
        for reference in (evidence.consent_evidence_ref, evidence.suppression_evidence_ref):
            if reference is not None and (
                not isinstance(reference, str) or not 8 <= len(reference) <= 128
                or any(c in reference for c in "@\r\n\t")
            ):
                raise ChannelEvidenceError("unsafe evidence reference")
        consent = evidence.consent_state
        suppression = evidence.suppression_state
        valid_identity = evidence.identity_bound is True
        age = now.astimezone(timezone.utc) - evidence.observed_at.astimezone(timezone.utc)
        evidence_recent = timedelta(0) <= age <= MAX_EVIDENCE_AGE

    if direct_hold:
        blockers.append("CRM_CONTACT_HOLD")
    if suppression == "suppressed":
        blockers.append("CANONICAL_SUPPRESSION_MATCH")
    elif suppression != "not_found":
        blockers.append("CANONICAL_SUPPRESSION_UNKNOWN")
    if consent == "opted_out":
        blockers.append("EXPLICIT_CHANNEL_OPT_OUT")
    elif consent != "verified_opt_in":
        blockers.append("EXPLICIT_CHANNEL_CONSENT_UNVERIFIED")
    if not valid_identity:
        blockers.append("CHANNEL_CONTACT_BINDING_UNVERIFIED")
    if not evidence_recent:
        blockers.append("CHANNEL_EVIDENCE_MISSING_OR_STALE")
    if suppression == "not_found" and (
        evidence is None or not evidence.suppression_evidence_ref
    ):
        blockers.append("NO_CANONICAL_SUPPRESSION_CHECK_RECEIPT")
    if consent == "verified_opt_in" and (
        evidence is None or not evidence.consent_evidence_ref
    ):
        blockers.append("NO_CANONICAL_CONSENT_RECEIPT")

    hard_block = direct_hold or suppression == "suppressed" or consent == "opted_out"
    preconditions_complete = (
        not hard_block and valid_identity and evidence_recent
        and consent == "verified_opt_in" and suppression == "not_found"
        and bool(evidence and evidence.consent_evidence_ref
                 and evidence.suppression_evidence_ref)
    )
    status = (
        "BLOCKED_BY_EVIDENCE" if hard_block else
        "REVIEW_ONLY_EVIDENCE_PRESENT" if preconditions_complete else
        "HOLD_MISSING_EVIDENCE"
    )
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "tenant_id": tenant, "prospect_id": pid, "channel": channel,
        "review_status": status,
        "canonical_contact_identity_verified": valid_identity and evidence_recent,
        "channel_consent_state": consent,
        "canonical_suppression_state": suppression,
        "evidence_recent": evidence_recent,
        "evidence_source": VERIFIED_SOURCE if evidence is not None else None,
        "contact_fields_disclosed": False,
        "consent_suppression_review_preconditions_met": preconditions_complete,
        "marketing_eligibility_proven": False,  # Other legal, transport and authority gates remain.
        "blockers": sorted(set(blockers)),
        "send_authorized": False, "followup_authorized": False,
        "subscription_created": False, "crm_mutation": False,
        "execution_authority": "none",
    }
