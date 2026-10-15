"""Verify root-signed independent GTM audit checkpoints, without issuing keys.

A checkpoint must be signed by a separate, pre-pinned first-party audit
authority and retained outside the reviewer ledger's writable location.
This code can verify one such object and produce a trusted compare token.
It does not perform remote storage, bootstrap any key or prove WORM custody.
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import json
import re
from typing import Any, Mapping
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

CHECKPOINT_SCHEMA = "empire.gtm_signed_external_checkpoint.v1"
DOMAIN = b"empire-gtm-external-audit-checkpoint-v1:"
FIELDS = frozenset((
    "schema_version", "audience", "tenant_id",
    "sequence", "chain_sha256", "issued_at", "checkpoint_revision",
))
HEX = re.compile(r"^[0-9a-f]{64}$")


def _signed(data: Mapping[str, Any]) -> bytes:
    return DOMAIN + json.dumps(
        dict(data), sort_keys=True, ensure_ascii=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("ascii")


def _signature(encoded: Any) -> bytes:
    if (not isinstance(encoded, str) or len(encoded) != 86
            or re.fullmatch(r"[A-Za-z0-9_-]+", encoded) is None):
        raise ValueError("invalid_external_checkpoint_signature")
    try:
        raw = base64.b64decode(
            encoded + "==", altchars=b"-_", validate=True,
        )
    except (ValueError, base64.binascii.Error) as exc:
        raise ValueError("invalid_external_checkpoint_signature") from exc
    if (len(raw) != 64 or
            base64.urlsafe_b64encode(raw).rstrip(b"=").decode() != encoded):
        raise ValueError("invalid_external_checkpoint_signature")
    return raw


def verify_external_gtm_audit_checkpoint(
    envelope: Mapping[str, Any], *,
    pinned_audit_signer_id: str,
    pinned_audit_public_key: bytes,
    expected_tenant: str,
    minimum_trusted_revision: int,
    as_of: datetime,
) -> dict[str, Any]:
    """Return the exact ledger-compatible checkpoint only if fully verified.

    The root signing key and monotonic minimum revision are required from
    outside the caller-supplied checkpoint and unrelated reviewer account.
    """
    if (not isinstance(envelope, Mapping)
            or set(envelope) != {"kid", "payload", "signature"}
            or envelope.get("kid") != pinned_audit_signer_id
            or not isinstance(pinned_audit_public_key, bytes)
            or len(pinned_audit_public_key) != 32
            or type(minimum_trusted_revision) is not int
            or minimum_trusted_revision < 1
            or not isinstance(as_of, datetime)
            or as_of.tzinfo is None):
        raise ValueError("separately_pinned_audit_anchor_required")
    try:
        if str(UUID(expected_tenant)) != expected_tenant:
            raise ValueError()
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("authenticated_audit_tenant_required") from exc
    data = envelope["payload"]
    if (not isinstance(data, Mapping)
            or set(data) != FIELDS
            or data["schema_version"] != CHECKPOINT_SCHEMA
            or data["audience"] != "empire-gtm-external-audit-anchor"
            or data["tenant_id"] != expected_tenant
            or type(data["checkpoint_revision"]) is not int
            or data["checkpoint_revision"] < minimum_trusted_revision
            or type(data["sequence"]) is not int
            or not 0 <= data["sequence"] <= 3000
            or not isinstance(data["chain_sha256"], str)
            or HEX.fullmatch(data["chain_sha256"]) is None
            or (data["sequence"] == 0 and
                data["chain_sha256"] != "0" * 64)):
        raise ValueError("invalid_or_rolled_back_external_audit_anchor")
    try:
        clock = datetime.fromisoformat(
            data["issued_at"].replace("Z", "+00:00")
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("invalid_checkpoint_issuance_time") from exc
    if clock.tzinfo is None or clock.utcoffset() is None:
        raise ValueError("checkpoint_clock_must_be_aware")
    clock = clock.astimezone(timezone.utc)
    if clock > as_of.astimezone(timezone.utc) + timedelta(minutes=5):
        raise ValueError("future_checkpoint_cannot_be_trusted")
    try:
        Ed25519PublicKey.from_public_bytes(
            pinned_audit_public_key
        ).verify(_signature(envelope.get("signature")), _signed(data))
    except InvalidSignature as exc:
        raise ValueError("checkpoint_signature_not_trusted") from exc
    return {
        "schema_version":"empire.gtm_external_audit_checkpoint.v1",
        "sequence":data["sequence"],
        "chain_sha256":data["chain_sha256"],
    }
