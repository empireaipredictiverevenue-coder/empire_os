"""Cryptographically gated, research-only owner ticket pickup + acknowledgement.

A delivery packet is a local outbox, not a dispatched task. An authenticated
owner may ACK a research request, but that NEVER promotes buyer data, grants
payment authority, authorises messaging or verifies a sale.
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Mapping
import json
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from empire_os.a2a_target_owner_handoff_v1 import SCHEMA as HANDOFF_SCHEMA

OUTBOX_SCHEMA = "empire.a2a.owner_research_pickup.v1"
RECEIPT_SCHEMA = "empire.a2a.owner_research_receipt.v1"
RESULT_SCHEMA = "empire.a2a.owner_research_receipt_review.v1"
OWNERS = {
    "buyer_scout": "CANONICAL_COMPANY_AND_BUYER_CAPACITY_REVIEW",
    "community_intent": "PERMITTED_SOURCE_TOPIC_REVIEW",
}
ACK_STATES = frozenset(("ACCEPTED_FOR_RESEARCH", "DECLINED", "EVIDENCE_REVIEW_AVAILABLE"))
_HEX = re.compile(r"^[0-9a-f]{24}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_NONCE = re.compile(r"^[A-Za-z0-9_-]{20,120}$")
_REF = re.compile(r"^[a-zA-Z0-9:_/.%-]{12,180}$")
RECEIPT_FIELDS = frozenset((
    "schema_version", "ticket_id", "ticket_sha256", "owner",
    "status", "occurred_at", "nonce", "source_snapshot_sha256",
    "evidence_reference_ids", "no_external_outbound", "execution_authority",
    "signature_b64url",
))
_TICKET_FIELDS = (
    "ticket_id", "target_id", "review_owner", "requested_capability", "sector",
    "market", "product", "target_roles_not_contact_identities", "exclude",
    "existing_public_atlas_source_ids", "source_research_gap",
    "suggested_research_queries_not_executed", "acceptance_criteria",
)


def _now(value: datetime | None) -> datetime:
    d = value or datetime.now(timezone.utc)
    if d.tzinfo is None or d.utcoffset() is None:
        raise ValueError("owner_review_clock_requires_timezone")
    return d.astimezone(timezone.utc)


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d.astimezone(timezone.utc) if d.tzinfo else None


def _hash(value: Mapping[str, Any]) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode()).hexdigest()


def _canon_ticket(ticket: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(ticket, Mapping):
        raise ValueError("invalid_owner_task")
    tid = ticket.get("ticket_id")
    owner = ticket.get("review_owner")
    if not isinstance(tid, str) or not _HEX.fullmatch(tid):
        raise ValueError("invalid_owner_ticket_id")
    if owner not in OWNERS or ticket.get("requested_capability") != OWNERS[owner]:
        raise ValueError("unexpected_owner_capability")
    if (ticket.get("state") != "PREPARED_NOT_DELIVERED"
            or ticket.get("may_call_external_api") is not False
            or ticket.get("may_write_canonical_crm") is not False
            or ticket.get("may_send_messages") is not False
            or ticket.get("owner_approval_required") is not True
            or ticket.get("dataset_or_social_post_identity_not_promoted") is not True):
        raise ValueError("owner_task_not_research_only")
    body = {key: ticket.get(key) for key in _TICKET_FIELDS}
    if not isinstance(body["target_id"], str) or not re.fullmatch(r"[a-f0-9]{20}", body["target_id"]):
        raise ValueError("invalid_target_binding")
    for k in ("sector", "market", "product"):
        if not isinstance(body[k], str) or not re.fullmatch(r"[a-z0-9_, .-]{2,90}", body[k]):
            raise ValueError("untrusted_sector_market_product")
    if not isinstance(body["acceptance_criteria"], str) or len(body["acceptance_criteria"]) > 500:
        raise ValueError("unbounded_acceptance_criteria")
    for k in ("target_roles_not_contact_identities", "exclude",
              "existing_public_atlas_source_ids", "suggested_research_queries_not_executed"):
        v = body[k]
        if (not isinstance(v, list) or len(v) > 12
                or any(not isinstance(w, str) or len(w) > 170 or
                       any(c in w for c in "<>{}\n\r\t") for w in v)):
            raise ValueError("untrusted_owner_research_terms")
    if type(body["source_research_gap"]) is not bool:
        raise ValueError("source_gap_boolean_required")
    return body


def make_owner_pickup_packets(handoff: Mapping[str, Any]) -> dict[str, Any]:
    if (not isinstance(handoff, Mapping)
            or handoff.get("schema_version") != HANDOFF_SCHEMA
            or handoff.get("execution_authority") != "NONE"
            or handoff.get("tasks_dispatched") != 0
            or handoff.get("messages_sent") != 0
            or handoff.get("buyer_record_writes") != 0
            or handoff.get("owner_queue_published") is not False):
        raise ValueError("untrusted_owner_handoff")
    tickets = handoff.get("handoff_tickets")
    if not isinstance(tickets, list) or len(tickets) > 20:
        raise ValueError("unbounded_owner_tickets")
    if len(tickets) != handoff.get("prepared_handoff_ticket_count"):
        raise ValueError("owner_ticket_count_mismatch")
    result: dict[str, list] = {owner: [] for owner in OWNERS}
    seen = set()
    for ticket in tickets:
        body = _canon_ticket(ticket)
        if body["ticket_id"] in seen:
            raise ValueError("duplicate_owner_ticket")
        seen.add(body["ticket_id"])
        result[body["review_owner"]].append({
            "ticket_id": body["ticket_id"],
            "ticket_sha256": _hash(body),
            "research_request": body,
            "research_only": True,
            "execution_state": "PICKUP_AVAILABLE_NOT_DELIVERED",
            "no_auto_dispatch": True,
            "no_contact_or_campaign_authority": True,
        })
    for values in result.values():
        values.sort(key=lambda d: d["ticket_id"])
    return {
        "schema_version": OUTBOX_SCHEMA, "mode": "OBSERVE",
        "source_report_schema": HANDOFF_SCHEMA,
        "pickup_by_owner": result,
        "pickup_count": sum(map(len, result.values())),
        "owner_dispatches": 0, "external_network_calls": 0,
        "queue_published_outside_isolated_worktree": False,
        "canonical_crm_writes": 0, "messages_sent": 0,
        "execution_authority": "NONE",
    }


def receipt_signing_bytes(receipt: Mapping[str, Any]) -> bytes:
    if not isinstance(receipt, Mapping) or set(receipt) != RECEIPT_FIELDS:
        raise ValueError("receipt_fields_not_exact")
    fields = {key: value for key, value in receipt.items()
              if key != "signature_b64url"}
    return json.dumps(fields, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf8")


def review_owner_receipts(
    pickup: Mapping[str, Any],
    receipts: list[Mapping[str, Any]],
    trusted_owner_public_keys: Mapping[str, bytes],
    *, now: datetime | None = None,
) -> dict[str, Any]:
    time = _now(now)
    if (not isinstance(pickup, Mapping)
            or pickup.get("schema_version") != OUTBOX_SCHEMA
            or pickup.get("execution_authority") != "NONE"
            or pickup.get("owner_dispatches") != 0
            or pickup.get("messages_sent") != 0):
        raise ValueError("untrusted_owner_pickup")
    owners = pickup.get("pickup_by_owner")
    if not isinstance(owners, Mapping) or set(owners) != set(OWNERS):
        raise ValueError("invalid_owner_pickup_map")
    tasks = {}
    for owner, items in owners.items():
        if not isinstance(items, list) or len(items) > 10:
            raise ValueError("invalid_owner_pickup_items")
        for item in items:
            if not isinstance(item, Mapping) or item.get("ticket_id") in tasks:
                raise ValueError("duplicate_owner_pickup")
            body = _canon_ticket(dict(item.get("research_request") or {},
                                      state="PREPARED_NOT_DELIVERED",
                                      may_call_external_api=False,
                                      may_write_canonical_crm=False,
                                      may_send_messages=False,
                                      owner_approval_required=True,
                                      dataset_or_social_post_identity_not_promoted=True))
            if body["review_owner"] != owner or item.get("ticket_sha256") != _hash(body):
                raise ValueError("owner_pickup_digest_mismatch")
            tasks[body["ticket_id"]] = item
    if not isinstance(receipts, list) or len(receipts) > 20:
        raise ValueError("unbounded_receipt_list")
    if not isinstance(trusted_owner_public_keys, Mapping):
        raise ValueError("trusted_owner_keys_invalid")
    if set(trusted_owner_public_keys) - set(OWNERS):
        raise ValueError("unknown_trusted_owner")
    if any(type(key) is not bytes or len(key) != 32 for key in trusted_owner_public_keys.values()):
        raise ValueError("invalid_trusted_owner_public_key")
    seen_nonces: set[tuple[str, str]] = set()
    seen_tickets: set[str] = set()
    accepted: dict[str, str] = {}
    rejected = []
    for receipt in receipts:
        if not isinstance(receipt, Mapping):
            rejected.append("BAD_RECEIPT_SHAPE")
            continue
        tid = receipt.get("ticket_id")
        task = tasks.get(tid)
        if not task:
            rejected.append("UNKNOWN_TICKET")
            continue
        owner = receipt.get("owner")
        if owner != task["research_request"]["review_owner"]:
            rejected.append("OWNER_MISMATCH")
            continue
        if tid in seen_tickets:
            rejected.append("DUPLICATE_TICKET_RECEIPT")
            continue
        if (receipt.get("schema_version") != RECEIPT_SCHEMA
                or receipt.get("ticket_sha256") != task["ticket_sha256"]
                or receipt.get("status") not in ACK_STATES
                or receipt.get("execution_authority") != "NONE"
                or receipt.get("no_external_outbound") is not True):
            rejected.append("UNVERIFIED_OWNER_CLAIM")
            continue
        when = _utc(receipt.get("occurred_at"))
        if when is None or not time - timedelta(hours=24) <= when <= time + timedelta(minutes=5):
            rejected.append("STALE_OR_FUTURE_OWNER_RECEIPT")
            continue
        nonce = receipt.get("nonce")
        if not isinstance(nonce, str) or not _NONCE.fullmatch(nonce):
            rejected.append("INVALID_OWNER_NONCE")
            continue
        if (owner, nonce) in seen_nonces:
            rejected.append("REPLAYED_OWNER_NONCE")
            continue
        if not isinstance(receipt.get("source_snapshot_sha256"), str) or not _SHA.fullmatch(receipt["source_snapshot_sha256"]):
            rejected.append("MISSING_OWNER_SOURCE_RECEIPT")
            continue
        refs = receipt.get("evidence_reference_ids")
        if not isinstance(refs, list) or len(refs) > 6 or any(
                not isinstance(ref, str) or not _REF.fullmatch(ref) for ref in refs):
            rejected.append("UNSAFE_EVIDENCE_REFERENCES")
            continue
        if receipt.get("status") == "EVIDENCE_REVIEW_AVAILABLE" and not refs:
            rejected.append("EVIDENCE_REF_REQUIRED")
            continue
        public = trusted_owner_public_keys.get(owner)
        if public is None:
            rejected.append("TRUSTED_OWNER_PUBLIC_KEY_NOT_CONFIGURED")
            continue
        try:
            payload = receipt_signing_bytes(receipt)
            signature = receipt.get("signature_b64url")
            if not isinstance(signature, str) or not re.fullmatch(r"[A-Za-z0-9_-]{85,90}", signature):
                raise ValueError("invalid_signature_encoding")
            raw = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
            Ed25519PublicKey.from_public_bytes(public).verify(raw, payload)
        except (InvalidSignature, ValueError, TypeError, UnicodeError):
            rejected.append("INVALID_OWNER_SIGNATURE")
            continue
        seen_nonces.add((owner, nonce))
        seen_tickets.add(tid)
        accepted[tid] = receipt["status"]
    return {
        "schema_version": RESULT_SCHEMA,
        "mode": "OBSERVE", "execution_authority": "NONE",
        "prepared_research_requests": len(tasks),
        "owner_public_keys_configured": sorted(trusted_owner_public_keys),
        "authenticated_owner_replies": len(accepted),
        "owner_research_accepted": sum(x == "ACCEPTED_FOR_RESEARCH" for x in accepted.values()),
        "owner_evidence_reviews_available": sum(x == "EVIDENCE_REVIEW_AVAILABLE" for x in accepted.values()),
        "owner_declines": sum(x == "DECLINED" for x in accepted.values()),
        "owner_receipts_rejected": len(rejected),
        "rejection_reason_codes": sorted(set(rejected)),
        "ticket_receipt_states": dict(sorted(accepted.items())),
        "still_awaiting_authenticated_owner_replies": len(tasks) - len(accepted),
        "buyer_identity_verified_by_this_protocol": False,
        "buyer_qualified_by_this_protocol": False,
        "purchase_intent_verified_by_this_protocol": False,
        "owner_task_dispatches_by_this_protocol": 0,
        "client_data_exported": False, "outbound_authority": False,
        "money_movement_authority": False,
    }
