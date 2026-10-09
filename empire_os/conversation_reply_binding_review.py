"""Deterministic Stage 3 reply identity review, integrated with Conversation OS.

Inputs are already-bounded evidence projections supplied by an authorised
caller; this module makes NO database or mail calls. A matching graph is
review-only: it never attests provider authenticity, tenant rights, buyer
intent, payment, or commercial execution.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from typing import Any, Mapping, Sequence
import re

MAX_ROWS = 100
MAX_LENGTH = 512
PARTICIPANTS = ("prospect_id", "entity_id", "buyer_id", "opportunity_id")
RFC_MESSAGE_ID = re.compile(r"^<[^\s<>@]{1,200}@[^\s<>@]{1,200}>$")
CONTACT_ADDRESS = re.compile(r"^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$")


def _text(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    return value.strip() if isinstance(value, str) and len(value) <= MAX_LENGTH else ""


def _rows(inputs: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    value = inputs.get(key, [])
    if not isinstance(value, (tuple, list)) or len(value) > MAX_ROWS:
        raise ValueError(f"{key} must be a bounded array")
    if any(not isinstance(r, Mapping) for r in value):
        raise ValueError(f"{key} contains non-record")
    return list(value)


def _matches(rows: Sequence[Mapping[str, Any]], **required: str) -> list[Mapping[str, Any]]:
    return [
        row for row in rows
        if all(_text(row, field) == expected for field, expected in required.items())
    ]


def _fingerprint(value: str) -> str:
    return "sha256:" + sha256(("empire-stage3-review:" + value).encode()).hexdigest()


def _unique(
    rows: Sequence[Mapping[str, Any]], *,
    missing: str, ambiguous: str, blockers: set[str],
) -> Mapping[str, Any] | None:
    if not rows:
        blockers.add(missing)
        return None
    if len(rows) != 1:
        blockers.add(ambiguous)
        return None
    return rows[0]


def review_identity_bindings(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Quarantine ambiguous relationships, never infer buyer authenticity."""
    if not isinstance(inputs, Mapping):
        raise ValueError("bounded identity evidence inputs required")
    replies = _rows(inputs, "replies")
    intents = _rows(inputs, "outbound_intents")
    conversations = _rows(inputs, "conversations")
    tenants = _rows(inputs, "tenant_authorities")
    contacts = _rows(inputs, "contact_authorities")
    sent = _rows(inputs, "original_outbound_headers")
    receipts = _rows(inputs, "provider_receipts")

    # Multiple recorded rows from a provider event may indicate replay or
    # competing intent claims; never arbitrarily select the first one.
    message_counts = Counter(
        _text(row, "provider_message_id") for row in replies
        if _text(row, "provider_message_id")
    )
    native_id_counts = Counter(
        _text(row, "message_id") for row in replies
        if _text(row, "message_id")
    )
    seen_ids = Counter(_text(row, "id") for row in replies if _text(row, "id"))
    output: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()

    for index, reply in enumerate(replies):
        blockers: set[str] = set()
        reply_id = _text(reply, "id")
        intent_id = _text(reply, "intent_id")
        provider_message_id = _text(reply, "provider_message_id")
        message_id = _text(reply, "message_id")
        in_reply_to = _text(reply, "in_reply_to")
        origin_contact = _text(reply, "normalized_from_contact").casefold()

        if not reply_id:
            blockers.add("REPLY_SOURCE_ID_MISSING")
        elif seen_ids[reply_id] != 1:
            blockers.add("REPLY_SOURCE_ID_DUPLICATED")
        if _text(reply, "direction").casefold() != "inbound":
            blockers.add("ORIGINAL_INBOUND_DIRECTION_UNVERIFIED")
        if not provider_message_id or not message_id or not in_reply_to:
            blockers.add("ORIGINAL_PROVIDER_THREAD_EVIDENCE_MISSING")
        elif not RFC_MESSAGE_ID.fullmatch(message_id) or not RFC_MESSAGE_ID.fullmatch(in_reply_to):
            blockers.add("INVALID_ORIGINAL_RFC_MESSAGE_CHAIN")
        if provider_message_id and message_counts[provider_message_id] != 1:
            blockers.add("DUPLICATE_PROVIDER_EVENT")
        if message_id and native_id_counts[message_id] != 1:
            blockers.add("DUPLICATE_RFC_MESSAGE_ID")
        if not origin_contact or not CONTACT_ADDRESS.fullmatch(origin_contact):
            blockers.add("CONTACT_ADDRESS_MISSING_OR_INVALID")

        intent = _unique(
            _matches(intents, id=intent_id) if intent_id else [],
            missing="OUTBOUND_INTENT_NOT_FOUND",
            ambiguous="OUTBOUND_INTENT_AMBIGUOUS", blockers=blockers,
        )
        if intent is not None and _text(intent, "status") not in (
            "sent", "delivered", "replied",
        ):
            blockers.add("OUTBOUND_INTENT_NOT_SENT_OR_SUPPRESSED")

        conv = _unique(
            _matches(conversations, outbound_intent_id=intent_id)
            if intent_id else [],
            missing="CONVERSATION_NOT_FOUND",
            ambiguous="CONVERSATION_AMBIGUOUS", blockers=blockers,
        )
        if conv is not None:
            if _text(conv, "channel") != "email" or _text(conv, "state") == "closed":
                blockers.add("CONVERSATION_NOT_ACTIVE_EMAIL")
            if intent is not None:
                paired = False
                for field in PARTICIPANTS:
                    left, right = _text(intent, field), _text(conv, field)
                    if left and right and left != right:
                        blockers.add("CANONICAL_PARTICIPANT_CONFLICT")
                    if bool(left) != bool(right):
                        blockers.add("CANONICAL_PARTICIPANT_SCOPE_INCOMPLETE")
                    if left and right and left == right:
                        paired = True
                if not paired:
                    blockers.add("CANONICAL_PARTICIPANT_LINK_MISSING")

        tenant = _unique(
            _matches(tenants, intent_id=intent_id, conversation_id=_text(conv, "id"))
            if intent_id and conv is not None else [],
            missing="TENANT_AUTHORITY_NOT_PROVEN",
            ambiguous="TENANT_AUTHORITY_AMBIGUOUS", blockers=blockers,
        )
        tenant_id = _text(tenant, "tenant_id") if tenant is not None else ""
        if tenant is not None and (
            not tenant_id or _text(tenant, "status") != "active"
            or not _text(tenant, "evidence_ref")
        ):
            blockers.add("TENANT_AUTHORITY_NOT_PROVEN")
        if _text(reply, "tenant_id") and _text(reply, "tenant_id") != tenant_id:
            blockers.add("CROSS_TENANT_REPLY_CONFLICT")

        contact = _unique(
            _matches(
                contacts, tenant_id=tenant_id, intent_id=intent_id,
                normalized_contact=origin_contact,
            ) if tenant_id and origin_contact and intent_id else [],
            missing="CANONICAL_CONTACT_NOT_PROVEN",
            ambiguous="CANONICAL_CONTACT_AMBIGUOUS", blockers=blockers,
        )
        if contact is not None and (
            not _text(contact, "contact_id")
            or _text(contact, "status") != "active"
            or not _text(contact, "evidence_ref")
        ):
            blockers.add("CANONICAL_CONTACT_NOT_PROVEN")

        source = _unique(
            _matches(sent, intent_id=intent_id, message_id=in_reply_to)
            if in_reply_to and intent_id else [],
            missing="ORIGINAL_OUTBOUND_RFC_PARENT_NOT_FOUND",
            ambiguous="ORIGINAL_OUTBOUND_RFC_PARENT_AMBIGUOUS", blockers=blockers,
        )
        if source is not None and not _text(source, "evidence_ref"):
            blockers.add("OUTBOUND_HEADER_PROVENANCE_MISSING")

        receipt = _unique(
            _matches(
                receipts, provider_message_id=provider_message_id,
                message_id=message_id, in_reply_to=in_reply_to,
            ) if provider_message_id and message_id and in_reply_to else [],
            missing="PROVIDER_RECEIPT_NOT_FOUND",
            ambiguous="PROVIDER_RECEIPT_AMBIGUOUS", blockers=blockers,
        )
        if receipt is not None and (
            not _text(receipt, "source_ref") or _text(receipt, "direction") != "inbound"
        ):
            blockers.add("PROVIDER_RECEIPT_PROVENANCE_INCOMPLETE")
        if receipt is not None and tenant_id and _text(receipt, "tenant_id") != tenant_id:
            blockers.add("CROSS_TENANT_RECEIPT_CONFLICT")

        reviewable = not blockers
        ordered = sorted(blockers)
        reason_counts.update(ordered)
        output.append({
            "record_ref": _fingerprint(reply_id or f"missing:{index}"),
            "status": (
                "STRUCTURALLY_REVIEWABLE_NOT_AUTHENTICATED"
                if reviewable else "QUARANTINED"
            ),
            "reason_codes": ordered,
            "structural_edges_unique": reviewable,
            "tenant_binding_reviewable": reviewable,
            "canonical_contact_reviewable": reviewable,
            "original_provider_authenticated": False,
            "buyer_intent_verified": False,
            "commercial_promotion_authorized": False,
        })

    ready = sum(row["structural_edges_unique"] for row in output)
    return {
        "schema": "empire.conversation_reply_binding_review.v1",
        "mode": "OBSERVE",
        "source": "caller_supplied_bounded_identity_projections",
        "candidate_count": len(output),
        "structurally_reviewable_count": ready,
        "quarantined_count": len(output) - ready,
        "reason_counts": dict(sorted(reason_counts.items())),
        "records": output,
        "production_original_provider_verification_performed": False,
        "tenant_authority_independently_attested": False,
        "buyer_intent_verified_count": 0,
        "canonical_messages_promoted": 0,
        "source_table_reads": 0,
        "contact_records_read_from_db": 0,
        "database_mutations": 0,
        "outbound_sent": False,
        "execution_authority": "none",
    }
