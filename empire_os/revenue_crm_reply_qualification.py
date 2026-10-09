"""Read-only qualification → canonical CRM review. No closer or CRM writes.

Composes the EXISTING Conversation OS qualification/freshness readers with
the existing CRM prospect read. Inbound signals are review candidates only:
a model or raw message cannot attest sender, tenant or buyer intent.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from empire_os.conversation_qualification import review_conversation_qualification
from empire_os.conversation_qualification_freshness import review_qualification_freshness

MAX_EVENTS = 200


def _id(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    return value.strip() if isinstance(value, str) and len(value) <= 256 else ""


def review_crm_reply_qualification(
    *,
    prospect: Mapping[str, Any],
    conversation: Mapping[str, Any] | None,
    events: Sequence[Mapping[str, Any]],
    stage3_source_health: Mapping[str, Any] | None,
    now: datetime,
) -> dict[str, Any]:
    """Produce a privacy-minimal, non-executing operator-review projection."""
    if now.tzinfo is None:
        raise ValueError("offset-aware clock required")
    if not isinstance(prospect, Mapping) or not _id(prospect, "prospect_id"):
        raise ValueError("canonical CRM prospect required")
    if not isinstance(events, (list, tuple)) or len(events) > MAX_EVENTS:
        raise ValueError("bounded canonical event batch required")
    if any(not isinstance(event, Mapping) for event in events):
        raise ValueError("event batch includes non-record")

    blockers: set[str] = set()
    signals: tuple[str, ...] = ()
    inbound = 0
    transcript_backed = 0
    fresh = False
    cid = _id(prospect, "conversation_id")
    if not cid:
        blockers.add("CRM_CONVERSATION_NOT_LINKED")
    if not isinstance(conversation, Mapping) or not _id(conversation, "id"):
        blockers.add("CANONICAL_CONVERSATION_NOT_READABLE")
    elif _id(conversation, "id") != cid:
        blockers.add("CRM_CONVERSATION_ID_MISMATCH")
    else:
        if _id(conversation, "channel").lower() != "email":
            blockers.add("CRM_CONVERSATION_NOT_EMAIL")
        if _id(conversation, "prospect_id") != _id(prospect, "prospect_id"):
            blockers.add("CRM_PROSPECT_IDENTITY_MISMATCH")
        if not _id(prospect, "tenant_id") or not _id(conversation, "tenant_id"):
            blockers.add("CRM_TENANT_SCOPE_UNAVAILABLE")
        elif _id(prospect, "tenant_id") != _id(conversation, "tenant_id"):
            blockers.add("CRM_TENANT_SCOPE_CONFLICT")

    relationship_valid = (
        bool(cid)
        and isinstance(conversation, Mapping)
        and _id(conversation, "id") == cid
        and _id(conversation, "channel").lower() == "email"
        and _id(conversation, "prospect_id") == _id(prospect, "prospect_id")
        and bool(_id(prospect, "tenant_id"))
        and _id(conversation, "tenant_id") == _id(prospect, "tenant_id")
    )
    if len(events) > 0 and not relationship_valid:
        blockers.add("QUALIFICATION_PREVIEW_WITHHELD_UNBOUND_IDENTITY")
    if relationship_valid:
        inbound_ids = [
            _id(row, "provider_event_id") for row in events
            if str(row.get("direction") or "").lower() == "inbound"
        ]
        if any(not value for value in inbound_ids):
            blockers.add("ORIGINAL_INBOUND_EVENT_ID_MISSING")
        if len(inbound_ids) != len(set(inbound_ids)):
            blockers.add("DUPLICATE_INBOUND_PROVIDER_EVENT")
        try:
            reviewed = review_conversation_qualification(events, conversation_id=cid)
            inbound = reviewed.inbound_event_count
            transcript_backed = reviewed.transcript_backed_inbound_count
            signals = reviewed.observed_signals
            blockers.update(reviewed.blockers)
            timing = review_qualification_freshness(
                reviewed, now=now.astimezone(timezone.utc),
            )
            fresh = timing.fresh_for_operator_review
            if not fresh:
                blockers.add("QUALIFICATION_EVIDENCE_STALE_OR_INVALID")
        except (ValueError, TypeError, AttributeError):
            blockers.add("QUALIFICATION_SOURCE_CONTRACT_INVALID")

    identity = stage3_source_health
    if not isinstance(identity, Mapping) or (
        identity.get("status") != "CODE_PATH_CURRENT_ORIGINAL_EVIDENCE_PENDING"
        or identity.get("execution_authority") != "none"
        or identity.get("review_only") is not True
        or identity.get("buyer_intent_verified") is not False
        or identity.get("original_provider_authentication_verified") is not False
        or identity.get("tenant_authority_verified") is not False
        or identity.get("canonical_contact_binding_verified") is not False
    ):
        blockers.add("STAGE3_SOURCE_INTEGRITY_UNVERIFIED")
    # A globally healthy identity planner cannot attest an individual contact.
    blockers.add("ORIGINAL_INBOUND_PROVIDER_AND_TENANT_PROOF_PENDING")
    blockers.add("CANONICAL_CONTACT_BINDING_NOT_VERIFIED")

    ordered = sorted(blockers)
    return {
        "schema": "empire.revenue_crm_reply_qualification_review.v1",
        "mode": "OBSERVE",
        "status": "BLOCKED_ORIGINAL_BUYER_PROOF",
        "read_only": True,
        "prospect_present": True,
        "conversation_binding_checked": bool(cid and isinstance(conversation, Mapping)),
        "inbound_event_count": inbound,
        "transcript_backed_inbound_count": transcript_backed,
        "candidate_qualification_signals_unverified": list(signals),
        "qualification_fresh_for_review": fresh,
        "blockers": ordered,
        "crm_operator_handoff_authorized": False,
        "canonical_buyer_authenticated": False,
        "tenant_authority_verified": False,
        "buyer_intent_verified": False,
        "crm_mutation": False,
        "closer_case_mutation": False,
        "outbound_sent": False,
        "payment_execution": False,
        "execution_authority": "none",
    }
