"""Offline first-party MTA handoff: trust-owner injected, no SMTP listener.

IMPORTANT: This code does not itself establish a trusted SMTP ingress, DKIM,
DMARC, SPF or canonical DB authority. It prepares a domain-separated signed
statement only when separately provided owner-managed, authenticated MTA
evidence, scoped canonical binding and a durable replay reservation all agree.
The signer belongs to a future restricted mail-ingress owner, NEVER to JEV.
No environment key loading, listener, network, mail send, MIME body persistence.
"""
from __future__ import annotations

import base64
import os
import stat
from pathlib import Path
from datetime import datetime, timezone
from email.parser import BytesHeaderParser
from email.policy import default as email_default
from hashlib import sha256
import json
import re
from typing import Any, Callable, Mapping
from uuid import UUID, uuid5

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from empire_os.conversation_reply_binding_review import RFC_MESSAGE_ID
from empire_os.jev_gtm_signed_transport_review import (
    AUDIENCE, DOMAIN, ISSUER, SCHEMA,
)

MAX_ORIGINAL_BYTES = 512 * 1024
MAX_HEADER_BYTES = 48 * 1024
ALIAS = re.compile(
    r"^reply\+([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})@mail\.empire-ai\.co\.uk$"
)
QUEUE = re.compile(r"^[A-Z0-9]{8,32}$")
KEY_ID = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
HEX = re.compile(r"^[0-9a-f]{64}$")
EVENT_NAMESPACE = UUID("086801c0-f146-4ccb-84fb-d124500b09b1")
BOUNDARY_FIELDS = frozenset({
    "mta_queue_id", "raw_message_sha256", "received_at",
    "source", "authenticated_local_peer",
    "trusted_authentication_result", "independent_evidence_id",
})
TENANT_FIELDS = frozenset({"tenant_id", "intent_id", "scope_verified"})


def _canonical_uuid(value: Any) -> str:
    try:
        result = str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("canonical identity UUID required") from None
    if value != result:
        raise ValueError("noncanonical identity UUID")
    return result


def _trusted_header(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 512:
        raise ValueError("singular original RFC message header required")
    if not RFC_MESSAGE_ID.fullmatch(value):
        raise ValueError("malformed original RFC message header")
    return value


def _headers(raw: bytes) -> tuple[str, str]:
    """Extract RFC chain from bounded original message bytes, not webhook JSON."""
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_ORIGINAL_BYTES:
        raise ValueError("bounded original message bytes required")
    pos = raw.find(b"\r\n\r\n")
    if pos < 0 or pos > MAX_HEADER_BYTES:
        raise ValueError("bounded CRLF-delimited RFC header block required")
    block = raw[:pos + 4]
    if b"\x00" in block:
        raise ValueError("NUL in original headers")
    parsed = BytesHeaderParser(policy=email_default).parsebytes(block)
    if parsed.defects:
        raise ValueError("RFC original header defects")
    for field in ("Message-ID", "In-Reply-To", "From"):
        if len(parsed.get_all(field, [])) != 1:
            raise ValueError("singular RFC thread headers required")
    mid = _trusted_header(str(parsed["Message-ID"]))
    parent = _trusted_header(str(parsed["In-Reply-To"]))
    if mid == parent:
        raise ValueError("original RFC message cannot reference itself")
    # MIME From is NOT treated as authenticated: trusted MTA records, not
    # untrusted Authentication-Results headers, are the sole verification input.
    return mid, parent


def prepare_owned_ingress_receipt(
    *,
    raw_message: bytes,
    envelope_recipient: str,
    mta_queue_id: str,
    trusted_mta_evidence: Callable[[str, str], Mapping[str, Any]],
    canonical_intent_binding: Callable[[str], Mapping[str, Any]],
    reserve_unique_event: Callable[[str, str], bool],
    signer: Ed25519PrivateKey,
    key_id: str,
    issued_at: datetime,
) -> dict[str, Any]:
    """Offline owner-bound callback: signer/keys never appear in the response.

    A receiver MUST authenticate its Unix peer and MTA event log out-of-band,
    and pin this callback to that independently audited evidence source. An
    arbitrary Python callback or signed MIME header alone is *not* proof.
    """
    if not isinstance(issued_at, datetime) or issued_at.tzinfo is None or issued_at.utcoffset() is None:
        raise ValueError("UTC-aware issue time required")
    if not isinstance(envelope_recipient, str) or not ALIAS.fullmatch(envelope_recipient):
        raise ValueError("exact reply alias SMTP envelope required")
    intent = _canonical_uuid(ALIAS.fullmatch(envelope_recipient).group(1))
    if not isinstance(mta_queue_id, str) or not QUEUE.fullmatch(mta_queue_id):
        raise ValueError("canonical MTA queue ID required")
    if not isinstance(signer, Ed25519PrivateKey):
        raise ValueError("restricted ingress Ed25519 signer required")
    if not isinstance(key_id, str) or not KEY_ID.fullmatch(key_id):
        raise ValueError("pinned ingress key identifier required")
    if not callable(trusted_mta_evidence) or not callable(canonical_intent_binding) or not callable(reserve_unique_event):
        raise ValueError("independent MTA, canonical binding and replay repository required")

    mid, parent = _headers(raw_message)
    fingerprint = sha256(raw_message).hexdigest()
    observation = trusted_mta_evidence(mta_queue_id, fingerprint)
    if not isinstance(observation, Mapping) or set(observation) != BOUNDARY_FIELDS:
        raise ValueError("independent MTA observation required")
    if (observation["mta_queue_id"] != mta_queue_id
            or observation["raw_message_sha256"] != fingerprint
            or observation["source"] != "postfix_trusted_ingress_log"
            or observation["authenticated_local_peer"] is not True
            or observation["trusted_authentication_result"] != "dmarc_aligned_pass"
            or not isinstance(observation["independent_evidence_id"], str)
            or not QUEUE.fullmatch(observation["independent_evidence_id"])):
        raise ValueError("MTA provenance or aligned sender domain unverified")
    received = observation["received_at"]
    if type(received) is not int:
        raise ValueError("trusted original SMTP receive time required")
    now = int(issued_at.astimezone(timezone.utc).timestamp())
    if not now - 300 <= received <= now:
        raise ValueError("trusted ingress time outside signing boundary")
    bound = canonical_intent_binding(intent)
    if not isinstance(bound, Mapping) or set(bound) != TENANT_FIELDS:
        raise ValueError("canonical intent-tenant binding evidence required")
    if bound["scope_verified"] is not True or _canonical_uuid(bound["intent_id"]) != intent:
        raise ValueError("canonical intent binding rejected")
    tenant = _canonical_uuid(bound["tenant_id"])

    event = str(uuid5(
        EVENT_NAMESPACE,
        f"{tenant}:{intent}:{mta_queue_id}:{fingerprint}",
    ))
    # The external mail-owner replay repository MUST be durable, atomic,
    # identity-restricted. Memory-only fixtures are never production proof.
    if reserve_unique_event(event, fingerprint) is not True:
        raise ValueError("ingress event replay or idempotency hold")
    claim = {
        "issuer": ISSUER,
        "audience": AUDIENCE,
        "event_id": event,
        "tenant_id": tenant,
        "intent_id": intent,
        "message_id": mid,
        "in_reply_to": parent,
        "received_at": received,
        "issued_at": now,
        "boundary": "first_party_smtp_ingress",
        "direction": "inbound",
        "smtp_result": "dmarc_aligned_pass",
        "raw_message_sha256": fingerprint,
    }
    encoded = DOMAIN + json.dumps(
        claim, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("ascii")
    signature = base64.urlsafe_b64encode(
        signer.sign(encoded)
    ).rstrip(b"=").decode("ascii")
    return {
        "schema_version": SCHEMA,
        "key_id": key_id,
        "claims": claim,
        "signature": signature,
    }


class ProtectedIngressReplayStore:
    """Durable, no-follow, O_EXCL replay reservation for an owned MTA process.

    The private directory must have been provisioned by the mail-transport
    owner with mode 0700 and must not be shared with JEV/HTTP workers.
    Reserving before signing fails closed after crashes: the original MTA
    owner must reconcile its spool rather than mint another event.
    """

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)

    def reserve_once(self, event_id: str, digest: str) -> bool:
        event = _canonical_uuid(event_id)
        if not isinstance(digest, str) or not HEX.fullmatch(digest):
            raise ValueError("SHA-256 ingress event digest required")
        folder = self.directory
        try:
            meta = folder.lstat()
        except OSError:
            raise ValueError("private owned ingress replay directory unavailable") from None
        if (not stat.S_ISDIR(meta.st_mode) or meta.st_uid != os.geteuid()
                or stat.S_IMODE(meta.st_mode) != 0o700):
            raise ValueError("untrusted ingress replay directory ownership or mode")
        if not hasattr(os, "O_NOFOLLOW"):
            raise ValueError("no-follow file creation unsupported")
        location = folder / (event + ".seen")
        descriptor = None
        try:
            descriptor = os.open(
                location,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
            )
        except FileExistsError:
            return False
        except OSError:
            raise ValueError("durable ingress replay reservation unavailable") from None
        try:
            view = memoryview((digest + "\n").encode("ascii"))
            while view:
                n = os.write(descriptor, view)
                if n <= 0:
                    raise OSError("incomplete ingress replay reservation")
                view = view[n:]
            os.fsync(descriptor)
        except OSError:
            # Keep the reserved file: an uncertain write must not allow
            # automatic duplicate signature issuance on retry.
            raise ValueError("durable ingress replay reservation uncertain") from None
        finally:
            os.close(descriptor)
        return True


def fixture_contract_summary(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Privacy-safe diagnostic projection only; do not log private envelope."""
    return {
        "schema_version": "empire.owned_ingress_prepared_receipt.v1",
        "mode": "OFFLINE_FIXTURE_ONLY",
        "cryptographic_envelope_formed": isinstance(envelope, Mapping)
        and envelope.get("schema_version") == SCHEMA,
        "actual_postfix_ingress_seen": False,
        "producer_credential_provisioned": False,
        "producer_deployed": False,
        "original_smtp_source_audited": False,
        "canonical_buyer_identity_proven": False,
        "suppression_clearance_verified": False,
        "verified_buyer_reply_count": None,
        "outbound_authorized": False,
        "mail_sent": False,
        "dns_modified": False,
        "execution_authority": "none",
    }
