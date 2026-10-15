"""Root-signed, tenant-scoped GTM human reviewer trust bundle verifier.

Prepared integration only; no keys created, no real reviewer provisioned,
no roster edited, no IAM rights changed. The root verifier keys, minimum
accepted revision, trusted tenant and live permission callback MUST come
from a separately controlled first-party authority (not a model or bundle).
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import json
import re
from typing import Any, Callable, Mapping
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from empire_os.gtm_signed_reviewer_gate import (
    GtmReviewerAttestationVerifier, ID, REVIEW_SCOPE,
)

BUNDLE_SCHEMA = "empire.gtm_reviewer_authority_bundle.v1"
SIGN_DOMAIN = b"empire-gtm-reviewer-authority-bundle-v1:"
_HEX = re.compile(r"^[a-f0-9]{64}$")
_KEY = re.compile(r"^[A-Za-z0-9_-]{3,96}$")
_ALLOWED_FIELDS = frozenset((
    "schema_version", "audience", "tenant_id", "revision", "issued_at",
    "expires_at", "reviewers",
))
_REVIEWER_FIELDS = frozenset((
    "reviewer_id", "key_id", "ed25519_public_key_b64url",
    "independent_principal_sha256", "scope", "status",
))


def _clock(s: Any) -> datetime:
    if not isinstance(s, str) or len(s) > 40:
        raise ValueError("invalid_authority_bundle_time")
    try:
        t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid_authority_bundle_time") from exc
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError("authority_bundle_requires_aware_clock")
    return t.astimezone(timezone.utc)


def _raw_b64(s: Any, size: int) -> bytes:
    if (not isinstance(s, str) or len(s) > 256 or not s
            or re.fullmatch(r"[A-Za-z0-9_-]+", s) is None):
        raise ValueError("invalid_reviewer_public_key_encoding")
    try:
        data = base64.b64decode(s + "=" * (-len(s) % 4),
                                altchars=b"-_", validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise ValueError("invalid_reviewer_public_key_encoding") from exc
    if (len(data) != size
            or base64.urlsafe_b64encode(data).rstrip(b"=").decode() != s):
        raise ValueError("noncanonical_reviewer_public_key")
    return data


def _signed_bytes(obj: Mapping[str, Any]) -> bytes:
    return SIGN_DOMAIN + json.dumps(
        dict(obj), sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("ascii")


def build_trusted_gtm_reviewer_verifier(
    envelope: Mapping[str, Any], *,
    pinned_authority_key_id: str,
    pinned_authority_public_key: bytes,
    expected_tenant: str,
    minimum_accepted_revision: int,
    current_membership: Callable[[str, str, str], bool],
    trusted_now: Callable[[], datetime] | None = None,
) -> GtmReviewerAttestationVerifier:
    """Verify first-party root-authorised roster, derive pinned reviewer gate.

    Trust inputs MUST be supplied by a secure issuer/service, never from
    user/agent messages. A bundle alone is NOT proof of genuine independent
    human identities; root policy and live membership remain necessary.
    """
    if (not isinstance(envelope, Mapping)
            or set(envelope) != {"kid", "payload", "signature"}
            or envelope.get("kid") != pinned_authority_key_id
            or not isinstance(envelope.get("payload"), Mapping)
            or not isinstance(pinned_authority_public_key, bytes)
            or len(pinned_authority_public_key) != 32
            or type(minimum_accepted_revision) is not int
            or minimum_accepted_revision < 1
            or not callable(current_membership)):
        raise ValueError("separately_pinned_reviewer_root_required")
    try:
        if str(UUID(expected_tenant)) != expected_tenant:
            raise ValueError()
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("authenticated_canonical_tenant_required") from exc
    clock = trusted_now or (lambda: datetime.now(timezone.utc))
    if not callable(clock):
        raise ValueError("trusted_authority_clock_required")
    payload = envelope["payload"]
    if (set(payload) != _ALLOWED_FIELDS
            or payload["schema_version"] != BUNDLE_SCHEMA
            or payload["audience"] != "empire-gtm-human-reviewer-authority"
            or payload["tenant_id"] != expected_tenant
            or type(payload["revision"]) is not int
            or payload["revision"] < minimum_accepted_revision):
        raise ValueError("invalid_or_rolled_back_reviewer_authority_bundle")
    issued = _clock(payload["issued_at"])
    expires = _clock(payload["expires_at"])
    current = clock()
    if not isinstance(current, datetime) or current.tzinfo is None:
        raise ValueError("trusted_authority_clock_required")
    current = current.astimezone(timezone.utc)
    if (issued > current + timedelta(minutes=5)
            or expires <= current or expires <= issued
            or expires - issued > timedelta(days=30)):
        raise ValueError("expired_or_future_reviewer_authority_bundle")
    try:
        signature = _raw_b64(envelope["signature"], 64)
        Ed25519PublicKey.from_public_bytes(
            pinned_authority_public_key
        ).verify(signature, _signed_bytes(payload))
    except InvalidSignature as exc:
        raise ValueError("untrusted_reviewer_roster_signature") from exc
    roster = payload["reviewers"]
    if not isinstance(roster, list) or not 1 <= len(roster) <= 32:
        raise ValueError("bounded_reviewer_roster_required")
    reviewer_ids = set()
    key_ids = set()
    principals = set()
    pinned: dict[str, tuple[str, bytes]] = {}
    active = set()
    for row in roster:
        if not isinstance(row, Mapping) or set(row) != _REVIEWER_FIELDS:
            raise ValueError("invalid_root_signed_reviewer_record")
        reviewer, key_id, principal = (
            row["reviewer_id"], row["key_id"],
            row["independent_principal_sha256"],
        )
        if (not isinstance(reviewer, str) or ID.fullmatch(reviewer) is None
                or not isinstance(key_id, str) or _KEY.fullmatch(key_id) is None
                or not isinstance(principal, str)
                or _HEX.fullmatch(principal) is None
                or row["scope"] != REVIEW_SCOPE
                or row["status"] not in ("ACTIVE", "REVOKED")):
            raise ValueError("invalid_reviewer_identity_or_scope")
        if reviewer in reviewer_ids or key_id in key_ids or principal in principals:
            raise ValueError("duplicate_human_principal_or_review_key")
        reviewer_ids.add(reviewer)
        key_ids.add(key_id)
        principals.add(principal)
        public = _raw_b64(row["ed25519_public_key_b64url"], 32)
        if row["status"] == "ACTIVE":
            pinned[key_id] = (reviewer, public)
            active.add(reviewer)
    if not pinned:
        raise ValueError("no_active_signed_reviewers")
    # Trust the outside current-membership checker, not the roster as a
    # stand-alone grant. Enforce expiry on EACH incoming signed review.
    def scope_check(reviewer: str, tenant: str, scope: str) -> bool:
        timestamp = clock()
        if not isinstance(timestamp, datetime) or timestamp.tzinfo is None:
            return False
        timestamp = timestamp.astimezone(timezone.utc)
        if (tenant != expected_tenant or scope != REVIEW_SCOPE
                or reviewer not in active or timestamp >= expires
                or timestamp < issued - timedelta(minutes=5)):
            return False
        try:
            return current_membership(reviewer, tenant, scope) is True
        except Exception:
            return False
    return GtmReviewerAttestationVerifier(
        pinned, active_reviewer_scope=scope_check,
    )
