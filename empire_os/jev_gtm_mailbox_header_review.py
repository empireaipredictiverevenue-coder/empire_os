"""Privacy-minimal, read-only matching of owned IMAP RFC headers to sent headers.

IMAP UIDVALIDITY, RFC Message-ID and Reply-To are structurally useful,
but they do NOT authenticate the SMTP sender, contact, tenant, or buying
intent. No message body, address, subject or RFC ID leaves this projection.
All row references use caller-owned HMAC key (never hash bare emails).
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import hmac
from typing import Any, Mapping
import re

from empire_os.owned_imap_mailbox import OwnedIMAPMailboxProvider, ID_PATTERN
from empire_os.conversation_reply_binding_review import RFC_MESSAGE_ID
from empire_os.empire_mailbox import _intent_from_values

MAX_READ = 25


def _reference(value: str, key: bytes) -> str:
    return "hmac-sha256:" + hmac.new(key, value.encode(), sha256).hexdigest()


def _rfc_header(row: Mapping[str, Any], field: str) -> str:
    raw = row.get(field)
    if not isinstance(raw, str) or len(raw) > 512:
        return ""
    cleaned = raw.strip()
    return cleaned if RFC_MESSAGE_ID.fullmatch(cleaned) else ""


def _mailbox_id(row: Mapping[str, Any], folder: str) -> str:
    raw = row.get("id")
    if not isinstance(raw, str):
        return ""
    match = ID_PATTERN.fullmatch(raw)
    return raw if match and match[1] == folder else ""


def review_owned_mailbox_headers(
    provider: OwnedIMAPMailboxProvider, *,
    key: bytes,
    limit: int = 25,
) -> dict[str, Any]:
    """Run an explicitly invoked IMAP read via existing sovereign provider.

    Caller must be the pre-authorised mailbox operator; no environment
    credential loading or account provisioning in this function.
    """
    if not isinstance(provider, OwnedIMAPMailboxProvider):
        raise ValueError("sovereign IMAP provider required")
    if type(limit) is not int or not 1 <= limit <= MAX_READ:
        raise ValueError("bounded mailbox review required")
    if not isinstance(key, bytes) or len(key) < 32:
        raise ValueError("separate operator HMAC key required")
    if provider.readiness().get("configured") is not True:
        raise ValueError("owned mailbox not configured")
    # The provider performs SELECT readonly / BODY.PEEK with partial bodies.
    # We discard bodies immediately; only bounded original RFC metadata
    # participates in this deterministic, noncommercial review.
    received = provider.list_received(limit=limit)
    sent = provider.list_sent(limit=limit)
    if (not isinstance(received, list) or not isinstance(sent, list)
            or len(received) > limit or len(sent) > limit
            or any(not isinstance(row, Mapping) for row in received + sent)):
        raise ValueError("invalid bounded IMAP projection")

    sent_uids = Counter(_mailbox_id(row, "sent") for row in sent
                        if _mailbox_id(row, "sent"))
    outgoing = Counter(
        _rfc_header(row, "message_id") for row in sent
        if _rfc_header(row, "message_id")
        and _mailbox_id(row, "sent")
        and sent_uids[_mailbox_id(row, "sent")] == 1
        and row.get("provider") == "owned_imap"
        and row.get("canonical_contact_identity_verified") is False
        and row.get("canonical_thread_identity_verified") is False
    )
    incoming = Counter(_rfc_header(row, "message_id") for row in received
                       if _rfc_header(row, "message_id"))
    received_uids = Counter(_mailbox_id(row, "inbox") for row in received
                            if _mailbox_id(row, "inbox"))
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(received):
        blockers: set[str] = set()
        if row.get("provider") != "owned_imap":
            blockers.add("NON_OWNED_IMAP_SOURCE_INVALID")
        uid = _mailbox_id(row, "inbox")
        if not uid:
            blockers.add("IMAP_INBOX_UIDVALIDITY_MISSING")
        elif received_uids[uid] != 1:
            blockers.add("DUPLICATE_IMAP_INBOX_UID")
        mid = _rfc_header(row, "message_id")
        if not mid:
            blockers.add("ORIGINAL_RFC_MESSAGE_ID_INVALID")
        elif incoming[mid] != 1:
            blockers.add("DUPLICATE_INBOUND_RFC_MESSAGE_ID")
        parent = _rfc_header(row, "in_reply_to")
        if not parent:
            blockers.add("ORIGINAL_RFC_PARENT_MISSING")
        elif outgoing[parent] != 1:
            blockers.add(
                "ORIGINAL_SENT_PARENT_AMBIGUOUS" if outgoing[parent] > 1
                else "ORIGINAL_SENT_PARENT_NOT_IN_BOUNDED_SAMPLE"
            )
        # A MIME header / sender Date / IMAP INTERNALDATE may be user set
        # through APPEND and is never a signed provider delivery event.
        if row.get("source_received_at_verified") is not False:
            blockers.add("MAILBOX_RECEIPT_AUTHORITY_CONTRACT_INVALID")
        if row.get("canonical_thread_identity_verified") is not False:
            blockers.add("MAILBOX_THREAD_AUTHORITY_CONTRACT_INVALID")
        if row.get("canonical_contact_identity_verified") is not False:
            blockers.add("MAILBOX_CONTACT_AUTHORITY_CONTRACT_INVALID")
        matching = outgoing.get(parent, 0) == 1 and not blockers
        # An apparent To alias is sender-controlled and may be forged.
        # Restrict alias extraction to the existing Empire mailbox helper.
        alias = _intent_from_values(row.get("to"))
        if not alias:
            blockers.add("CANONICAL_REPLY_ALIAS_MISSING")
        # Readability of a sent+received RFC pair is *not* evidence that a
        # provider authenticated origin, source contact, buyer or tenant.
        blockers.add("ORIGINAL_PROVIDER_AUTHENTICATION_NOT_ATTESTED")
        blockers.add("CANONICAL_TENANT_CONTACT_BINDING_NOT_ATTESTED")
        rows.append({
            "record_ref": _reference(uid if uid else f"invalid:{index}", key),
            "intent_alias_ref": _reference(alias, key) if alias else None,
            "rfc_parent_ref": _reference(parent, key) if parent else None,
            "sent_rfc_parent_unique": bool(matching),
            "structural_match_not_authentication": bool(matching),
            "status": "STRUCTURAL_REVIEW_ONLY" if matching else "QUARANTINED",
            "blockers": sorted(blockers),
            "original_provider_authenticated": False,
            "canonical_contact_verified": False,
            "tenant_binding_verified": False,
            "positive_buyer_intent_verified": False,
            "outbound_authorized": False,
        })

    rows.sort(key=lambda value: value["record_ref"])
    return {
        "schema_version": "empire.jev.owned_mailbox_header_review.v1",
        "mode": "OBSERVE",
        "provider": "owned_imap",
        "received_header_rows": len(received),
        "sent_header_rows": len(sent),
        "structurally_reviewable_count": sum(
            row["status"] == "STRUCTURAL_REVIEW_ONLY" for row in rows
        ),
        "rows": rows,
        "inbox_sample_complete": False,
        "provider_receipts_authenticated": False,
        "canonical_identity_authenticated": False,
        "commercial_buyer_reply_count": None,
        "contact_suppression_clearance": False,
        "outbound_authorized": False,
        "database_mutations": False,
        "mailbox_mutations": False,
        "execution_authority": "none",
    }


def compare_owned_mailbox_to_crm_candidates(
    mailbox: Mapping[str, Any],
    crm_candidates: Mapping[str, Any],
    *, key: bytes,
) -> dict[str, Any]:
    """Tenant-scoped CRM candidate vs unbound IMAP aliases, review only.

    The CRM reader proves its own tenant session scope; the IMAP mailbox
    preview does NOT. Matching caller-controllable alias is only a hint.
    """
    if not isinstance(key, bytes) or len(key) < 32:
        raise ValueError("separate operator HMAC key required")
    if (not isinstance(mailbox, Mapping)
            or mailbox.get("schema_version") != "empire.jev.owned_mailbox_header_review.v1"
            or mailbox.get("execution_authority") != "none"
            or mailbox.get("provider_receipts_authenticated") is not False
            or mailbox.get("canonical_identity_authenticated") is not False
            or mailbox.get("outbound_authorized") is not False
            or not isinstance(mailbox.get("rows"), list)
            or not isinstance(crm_candidates, Mapping)
            or crm_candidates.get("schema_version") != "empire.jev.reply_candidate_review.v1"
            or crm_candidates.get("execution_authority") != "none"
            or crm_candidates.get("send_authorized") is not False
            or crm_candidates.get("genuine_buying_conversations_verified") is not None
            or not isinstance(crm_candidates.get("items"), list)):
        raise ValueError("trusted read-only candidate review packets required")
    alias_counts = Counter()
    for item in mailbox["rows"]:
        if not isinstance(item, Mapping) or item.get("outbound_authorized") is not False:
            raise ValueError("unsafe mailbox reply record")
        opaque = item.get("intent_alias_ref")
        if opaque is not None:
            if not isinstance(opaque, str) or not re.fullmatch(r"hmac-sha256:[0-9a-f]{64}", opaque):
                raise ValueError("invalid mailbox alias reference")
            alias_counts[opaque] += 1
    results = []
    for item in crm_candidates["items"]:
        if not isinstance(item, Mapping) or item.get("outbound_authorized") is not False:
            raise ValueError("unsafe canonical reply candidate")
        raw = item.get("intent_ref")
        if not isinstance(raw, str):
            raise ValueError("missing canonical intent ref")
        alias_ref = _reference(raw, key)
        count = alias_counts.get(alias_ref, 0)
        results.append({
            "candidate_ref": _reference(str(item.get("reply_ref") or ""), key),
            "mailbox_alias_matching_rows": count,
            "linkage_status": (
                "ALIAS_UNIQUE_UNAUTHENTICATED" if count == 1 else
                "ALIAS_AMBIGUOUS_UNAUTHENTICATED" if count > 1 else
                "NO_ALIAS_MATCH_IN_BOUNDED_INBOX"
            ),
            "original_provider_authenticated": False,
            "canonical_tenant_contact_verified": False,
            "positive_buyer_reply_verified": False,
        })
    return {
        "schema_version": "empire.jev.mailbox_crm_candidate_alignment.v1",
        "mode": "OBSERVE",
        "candidate_count": len(results),
        "rows": results,
        "tenant_binding_proven_across_sources": False,
        "original_provider_authenticated": False,
        "buyer_conversation_count_verified": None,
        "recognized_revenue": None,
        "contact_permission_granted": False,
        "outbound_authorized": False,
        "execution_authority": "none",
    }
