"""Read-only validation of signed *first-party SMTP observation* receipts.

Cryptography authenticates a pinned signing key's assertion, NOT the truth
of that assertion or a sender/contact/tenant. The separate mail-transport
owner must secure issuer key custody, collect evidence at a trusted ingress
boundary and approve deployment. JEV has NO receipt minting functionality.
"""
from __future__ import annotations

import base64
import binascii
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
import re
from typing import Any, Mapping, Sequence
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from empire_os.conversation_reply_binding_review import RFC_MESSAGE_ID
from empire_os.jev_gtm_mailbox_header_review import _reference

SCHEMA = "empire.jev.signed_ingress_observation.v1"
REPORT = "empire.jev.signed_ingress_review.v1"
ISSUER = "empire-owned-mail-ingress"
AUDIENCE = "empire-jev-transport-observation"
DOMAIN = b"EMPIRE_JEV_SIGNED_TRANSPORT_OBSERVATION_V1\x00"
MAX_RECEIPTS = 25
ALLOWED_SKEW_SECONDS = 30
MAX_INGRESS_DELAY_SECONDS = 300
MAX_RECEIPT_AGE_SECONDS = 7 * 86400
KEY_ID = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
HEX = re.compile(r"^[0-9a-f]{64}$")
OPAQUE = re.compile(r"^hmac-sha256:[0-9a-f]{64}$")
RECEIPT_FIELDS = frozenset({"schema_version", "key_id", "claims", "signature"})
CLAIM_FIELDS = frozenset({
    "issuer", "audience", "event_id", "tenant_id", "intent_id",
    "message_id", "in_reply_to", "received_at", "issued_at",
    "boundary", "direction", "smtp_result", "raw_message_sha256",
})


def _canonical_uuid(value: Any) -> str:
    try:
        expected = str(UUID(value))
    except (ValueError, AttributeError, TypeError):
        raise ValueError("canonical transport UUID required") from None
    if value != expected:
        raise ValueError("noncanonical transport UUID")
    return expected


def _url64(value: str) -> bytes:
    if not isinstance(value, str) or not value or len(value) > 200 or not re.fullmatch(
        r"[A-Za-z0-9_-]+", value
    ):
        raise ValueError("invalid signed observation signature")
    try:
        binary = base64.b64decode(
            value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
        )
    except (ValueError, binascii.Error):
        raise ValueError("invalid signed observation signature") from None
    if base64.urlsafe_b64encode(binary).rstrip(b"=").decode("ascii") != value:
        raise ValueError("noncanonical signed observation signature")
    return binary


def _keys(allowed: Mapping[str, bytes | Ed25519PublicKey]) -> dict[str, Ed25519PublicKey]:
    if not isinstance(allowed, Mapping) or not 1 <= len(allowed) <= 8:
        raise ValueError("pinned SMTP attestation public keys required")
    keys: dict[str, Ed25519PublicKey] = {}
    for key_id, raw in allowed.items():
        if not isinstance(key_id, str) or not KEY_ID.fullmatch(key_id):
            raise ValueError("invalid pinned SMTP key identifier")
        if isinstance(raw, Ed25519PublicKey):
            key = raw
        elif isinstance(raw, bytes) and len(raw) == 32:
            key = Ed25519PublicKey.from_public_bytes(raw)
        else:
            raise ValueError("invalid pinned SMTP public key")
        keys[key_id] = key
    return keys


def _message(claims: Mapping[str, Any]) -> bytes:
    # Canonical bytes are fixed by the verifier, never supplied by the caller.
    return DOMAIN + json.dumps(
        claims, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def inspect_signed_ingress_receipts(
    mailbox_review: Mapping[str, Any],
    envelopes: Sequence[Mapping[str, Any]], *,
    expected_tenant_id: str,
    pinned_ingress_keys: Mapping[str, bytes | Ed25519PublicKey],
    operator_hmac_key: bytes,
    as_of: datetime,
) -> dict[str, Any]:
    """Match externally signed transport assertions to HMAC-only IMAP rows.

    Caller must independently authenticate the tenant and supply the pinned
    first-party transport key. There is no credential or key lookup/fallback.
    Reject tampering rather than silently excluding malformed signed input.
    """
    if (not isinstance(mailbox_review, Mapping)
            or mailbox_review.get("schema_version") != "empire.jev.owned_mailbox_header_review.v1"
            or mailbox_review.get("mode") != "OBSERVE"
            or mailbox_review.get("provider") != "owned_imap"
            or mailbox_review.get("execution_authority") != "none"
            or mailbox_review.get("provider_receipts_authenticated") is not False
            or mailbox_review.get("canonical_identity_authenticated") is not False
            or mailbox_review.get("outbound_authorized") is not False
            or mailbox_review.get("commercial_buyer_reply_count") is not None
            or not isinstance(mailbox_review.get("rows"), list)
            or len(mailbox_review["rows"]) > MAX_RECEIPTS):
        raise ValueError("bounded unauthenticated source review required")
    if not isinstance(operator_hmac_key, bytes) or len(operator_hmac_key) < 32:
        raise ValueError("independent operator HMAC key required")
    if (not isinstance(as_of, datetime) or as_of.tzinfo is None
            or as_of.utcoffset() is None):
        raise ValueError("timezone-aware attestation review required")
    if not isinstance(envelopes, (tuple, list)) or len(envelopes) > MAX_RECEIPTS:
        raise ValueError("bounded signed receipt batch required")
    tenant = _canonical_uuid(expected_tenant_id)
    keys = _keys(pinned_ingress_keys)
    now = int(as_of.astimezone(timezone.utc).timestamp())
    rows = mailbox_review["rows"]
    by_triplet: dict[tuple[str, str, str], list[Mapping[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("invalid mailbox observation row")
        if (row.get("original_provider_authenticated") is not False
                or row.get("positive_buyer_intent_verified") is not False
                or row.get("tenant_binding_verified") is not False
                or row.get("canonical_contact_verified") is not False
                or row.get("outbound_authorized") is not False):
            raise ValueError("forged original mailbox authority")
        triplet = tuple(row.get(k) for k in (
            "inbound_rfc_ref", "rfc_parent_ref", "intent_alias_ref"
        ))
        if all(isinstance(v, str) and OPAQUE.fullmatch(v) for v in triplet):
            by_triplet.setdefault(triplet, []).append(row)
    seen_ids: set[str] = set()
    seen_triplets: set[tuple[str, str, str]] = set()
    matched: list[dict[str, Any]] = []
    unmatched = 0
    for envelope in envelopes:
        if not isinstance(envelope, Mapping) or set(envelope) != RECEIPT_FIELDS:
            raise ValueError("malformed signed transport envelope")
        kid = envelope["key_id"]
        if not isinstance(kid, str) or kid not in keys:
            raise ValueError("untrusted transport issuer key")
        claims = envelope["claims"]
        if not isinstance(claims, Mapping) or set(claims) != CLAIM_FIELDS:
            raise ValueError("malformed signed transport claims")
        signature = _url64(envelope["signature"])
        if len(signature) != 64:
            raise ValueError("invalid Ed25519 signature size")
        try:
            keys[kid].verify(signature, _message(claims))
        except InvalidSignature:
            raise ValueError("transport signature verification failed") from None
        if (claims["issuer"] != ISSUER or claims["audience"] != AUDIENCE
                or claims["boundary"] != "first_party_smtp_ingress"
                or claims["direction"] != "inbound"
                or claims["smtp_result"] != "dmarc_aligned_pass"):
            raise ValueError("incorrect signed transport scope or asserted receipt state")
        event_id = _canonical_uuid(claims["event_id"])
        if _canonical_uuid(claims["tenant_id"]) != tenant:
            raise ValueError("signed transport tenant assertion mismatch")
        intent = _canonical_uuid(claims["intent_id"])
        message_id = claims["message_id"]
        parent = claims["in_reply_to"]
        if (not isinstance(message_id, str) or not RFC_MESSAGE_ID.fullmatch(message_id)
                or not isinstance(parent, str) or not RFC_MESSAGE_ID.fullmatch(parent)
                or message_id == parent):
            raise ValueError("invalid signed RFC message chain")
        raw_digest = claims["raw_message_sha256"]
        if not isinstance(raw_digest, str) or not HEX.fullmatch(raw_digest):
            raise ValueError("missing signed raw-message digest")
        issued, received = claims["issued_at"], claims["received_at"]
        if type(issued) is not int or type(received) is not int:
            raise ValueError("integer transport receipt time required")
        if (issued < received or issued - received > MAX_INGRESS_DELAY_SECONDS
                or issued > now + ALLOWED_SKEW_SECONDS
                or received > now + ALLOWED_SKEW_SECONDS
                or now - issued > MAX_RECEIPT_AGE_SECONDS):
            raise ValueError("stale or future signed transport observation")
        if event_id in seen_ids:
            raise ValueError("duplicate signed ingress event")
        seen_ids.add(event_id)
        triplet = (
            _reference(message_id, operator_hmac_key),
            _reference(parent, operator_hmac_key),
            _reference(intent, operator_hmac_key),
        )
        if triplet in seen_triplets:
            raise ValueError("multiple signed attestations for same RFC recipient chain")
        seen_triplets.add(triplet)
        matching = by_triplet.get(triplet, [])
        if len(matching) != 1:
            unmatched += 1
            continue
        row = matching[0]
        if (row.get("sent_rfc_parent_unique") is not True
                or row.get("structural_match_not_authentication") is not True
                or row.get("status") != "STRUCTURAL_REVIEW_ONLY"
                or not isinstance(row.get("blockers"), list)
                or set(row["blockers"]) != {
                    "ORIGINAL_PROVIDER_AUTHENTICATION_NOT_ATTESTED",
                    "CANONICAL_TENANT_CONTACT_BINDING_NOT_ATTESTED",
                }):
            unmatched += 1
            continue
        matched.append({
            "record_ref": row["record_ref"],
            "ingress_event_ref": _reference(event_id, operator_hmac_key),
            "signed_transport_assertion_valid": True,
            "mailbox_rfc_chain_structurally_matched": True,
            "independent_ingress_logs_read_by_jev": False,
            "producer_assertion_factually_audited": False,
            "canonical_tenant_contact_verified": False,
            "suppression_clearance_verified": False,
            "positive_buyer_intent_verified": False,
            "outbound_authorized": False,
        })
    matched.sort(key=lambda row: row["record_ref"])
    return {
        "schema_version": REPORT,
        "mode": "OBSERVE",
        "signed_receipts_examined": len(envelopes),
        "signed_assertions_matched_to_imap_headers": len(matched),
        "unmatched_signed_assertions": unmatched,
        "rows": matched,
        "cryptographic_signature_checked": True,
        "trusted_ingress_producer_live_deployment_audited": False,
        "original_smtp_provider_authentication_independently_proven": False,
        "canonical_tenant_contact_binding_verified": False,
        "buyer_reply_count_verified": None,
        "recognized_revenue": None,
        "suppression_clearance_verified": False,
        "outbound_authorized": False,
        "mailbox_mutations": False,
        "database_mutations": False,
        "execution_authority": "none",
    }
