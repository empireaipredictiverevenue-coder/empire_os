"""Original PRIME owner-signed source intake PRE-FLIGHT (pure, OBSERVE only).

Reuses EmpireOS' pinned Ed25519 gate pattern. It does NOT read provider data,
install issuer credentials, operate a replay ledger, validate buyer truth or
grant an ingestion, model, financial, messaging or trading permission.

Requires trusted first-party issuer keys, active owner/tenant authority,
canonical binding and source custody lookups supplied by ORIGINAL owners.
Those callbacks are not manufactured from the signed receipt.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
import base64
import binascii
import json
import re
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from empire_os.prime_universal_evidence_fusion import (
    RECEIPT_SCHEMA, OWNER_CLASSES, MAX_RECEIPTS, _digest, _validated,
    PrimeFusionHold, review_prime_universal_evidence,
    summarize_prime_founder_evidence,
)

SCHEMA = "empire.prime.signed_owner_evidence_preflight.v1"
SIGNED_SCHEMA = "empire.prime.signed_original_owner_summary.v1"
AUDIENCE = "empire-prime-owner-evidence-observe"
SCOPE = "predictive:owner-evidence:review"
DOMAIN = b"empire-prime-owner-evidence-ed25519-v1:"
ENVELOPE_FIELDS = frozenset(("kid", "payload", "signature"))
SIGNED_FIELDS = frozenset((
    "schema_version", "audience", "scope", "issuer_owner",
    "tenant_scope_sha256", "issued_at", "expires_at", "nonce", "receipt",
))
_ID = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
_NONCE = re.compile(r"^[A-Za-z0-9_-]{24,96}$")
MAX_TTL = timedelta(minutes=5)


class OwnerSignatureHold(ValueError):
    """Signed owner receipt fails original security/custody preflight."""


def _utc(value: Any, field: str) -> datetime:
    if type(value) is not str or len(value) > 40:
        raise OwnerSignatureHold(field + "_invalid_UTC")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        raise OwnerSignatureHold(field + "_invalid_UTC") from None
    if stamp.tzinfo is None or stamp.utcoffset() != timedelta(0):
        raise OwnerSignatureHold(field + "_UTC_required")
    return stamp.astimezone(timezone.utc)


def _canonical(payload: Mapping[str, Any]) -> bytes:
    return DOMAIN + json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("ascii")


def _sig(raw: Any) -> bytes:
    if type(raw) is not str or len(raw) != 86 or re.fullmatch(r"[A-Za-z0-9_-]{86}", raw) is None:
        raise OwnerSignatureHold("invalid_canonical_Ed25519_signature")
    try:
        binary = base64.b64decode(raw + "==", altchars=b"-_", validate=True)
    except (ValueError, binascii.Error):
        raise OwnerSignatureHold("invalid_canonical_Ed25519_signature") from None
    if (len(binary) != 64
        or base64.urlsafe_b64encode(binary).rstrip(b"=").decode("ascii") != raw):
        raise OwnerSignatureHold("invalid_canonical_Ed25519_signature")
    return binary


class PrimeOwnerSignatureVerifier:
    """Owner-prepared sealed metadata validation, not independent live source proof.

    All callbacks must be from separately authenticated ORIGINAL owner systems.
    The verifier is incapable of asserting persistent replay prevention; that
    remains a blocked prerequisite to admitting live owner evidence.
    """

    def __init__(
        self, *,
        trusted_owner_public_keys: Mapping[str, tuple[str, bytes]],
        owner_scope_active: Callable[[str, str, str], bool],
        canonical_binding_current: Callable[[str, str, str, datetime], bool],
        source_custody_current: Callable[[str, str, str, str, str, datetime], bool],
    ) -> None:
        if (not callable(owner_scope_active) or not callable(canonical_binding_current)
            or not callable(source_custody_current)
            or not isinstance(trusted_owner_public_keys, Mapping)
            or not 1 <= len(trusted_owner_public_keys) <= 50):
            raise OwnerSignatureHold("original_owner_security_dependencies_required")
        pinned: dict[str, tuple[str, Ed25519PublicKey]] = {}
        for kid, entry in trusted_owner_public_keys.items():
            if (type(kid) is not str or not _ID.fullmatch(kid)
                or type(entry) is not tuple or len(entry) != 2):
                raise OwnerSignatureHold("invalid_trusted_owner_key_binding")
            owner, public = entry
            if (owner not in OWNER_CLASSES or type(public) is not bytes
                or len(public) != 32):
                raise OwnerSignatureHold("invalid_trusted_owner_key_binding")
            try:
                pinned[kid] = (owner, Ed25519PublicKey.from_public_bytes(public))
            except ValueError:
                raise OwnerSignatureHold("invalid_trusted_owner_key_binding") from None
        self._pinned = pinned
        self._owner_scope_active = owner_scope_active
        self._canonical_binding_current = canonical_binding_current
        self._source_custody_current = source_custody_current

    def _verify_one(
        self, envelope: Mapping[str, Any], *, tenant_id: str, now: datetime,
    ) -> tuple[dict[str, Any], str]:
        if (type(envelope) is not dict or set(envelope) != ENVELOPE_FIELDS
            or type(envelope.get("kid")) is not str
            or envelope["kid"] not in self._pinned
            or type(envelope.get("payload")) is not dict):
            raise OwnerSignatureHold("unknown_or_malformed_original_owner_envelope")
        payload = envelope["payload"]
        if set(payload) != SIGNED_FIELDS:
            raise OwnerSignatureHold("exact_original_owner_signed_fields_required")
        owner, public_key = self._pinned[envelope["kid"]]
        if (payload["schema_version"] != SIGNED_SCHEMA
            or payload["audience"] != AUDIENCE
            or payload["scope"] != SCOPE
            or type(payload["issuer_owner"]) is not str
            or payload["issuer_owner"] != owner
            or payload["tenant_scope_sha256"] != _digest(tenant_id)):
            raise OwnerSignatureHold("wrong_audience_owner_or_tenant")
        nonce = payload["nonce"]
        if type(nonce) is not str or not _NONCE.fullmatch(nonce):
            raise OwnerSignatureHold("signed_nonce_required")
        issued = _utc(payload["issued_at"], "issued_at")
        expires = _utc(payload["expires_at"], "expires_at")
        if (issued > now or expires <= now or expires <= issued
            or expires - issued > MAX_TTL):
            raise OwnerSignatureHold("expired_or_future_owner_signature")
        receipt = payload["receipt"]
        if type(receipt) is not dict or receipt.get("schema_version") != RECEIPT_SCHEMA:
            raise OwnerSignatureHold("original_owner_receipt_contract_required")
        if (receipt.get("owner") != owner
            or receipt.get("tenant_scope_sha256") != payload["tenant_scope_sha256"]):
            raise OwnerSignatureHold("signed_receipt_owner_or_tenant_conflict")
        try:
            raw_signature = _sig(envelope["signature"])
            public_key.verify(raw_signature, _canonical(payload))
        except (InvalidSignature, ValueError, TypeError, OverflowError):
            raise OwnerSignatureHold("original_owner_signature_invalid") from None
        try:
            original = _validated(receipt, tenant_digest=_digest(tenant_id), as_of=now)
        except PrimeFusionHold as exc:
            raise OwnerSignatureHold("original_evidence_contract_" + str(exc)) from None
        # Only ORIGINAL first-party authorities may supply these checks. A
        # signature over self-declared rights/status is NEVER sufficient.
        try:
            active = self._owner_scope_active(owner, tenant_id, SCOPE) is True
            binding = self._canonical_binding_current(
                tenant_id, original["entity_sha256"],
                original["tenant_binding_sha256"], now,
            ) is True
            custody = self._source_custody_current(
                owner, tenant_id, original["source_sha256"],
                original["origin_sha256"], original["event_sha256"], now,
            ) is True
        except Exception:
            raise OwnerSignatureHold("original_authority_reader_unavailable") from None
        if not active:
            raise OwnerSignatureHold("original_owner_scope_not_active")
        if not binding:
            raise OwnerSignatureHold("canonical_tenant_entity_binding_unverified")
        if not custody:
            raise OwnerSignatureHold("original_source_rights_or_custody_unverified")
        return original, owner + ":" + nonce

    def review(
        self, *, signed_envelopes: Sequence[Mapping[str, Any]],
        tenant_id: str, as_of: datetime,
    ) -> dict[str, Any]:
        """All-or-nothing signature/custody preflight; NO live ingestion.

        No durable nonce reservation is possible here. This method rejects
        duplicates *inside one batch* but never asserts inter-batch replay
        protection, authenticated production issuer configuration or consent.
        """
        if (type(signed_envelopes) not in (list, tuple)
            or len(signed_envelopes) > MAX_RECEIPTS):
            raise OwnerSignatureHold("bounded_original_owner_envelopes_required")
        if type(tenant_id) is not str or not tenant_id.strip():
            raise OwnerSignatureHold("trusted_tenant_context_required")
        if not isinstance(as_of, datetime) or as_of.tzinfo is None or as_of.utcoffset() is None:
            raise OwnerSignatureHold("trusted_UTC_now_required")
        now = as_of.astimezone(timezone.utc)
        verified: list[dict[str, Any]] = []
        used_nonces: set[str] = set()
        used_events: set[str] = set()
        for envelope in signed_envelopes:
            original, nonce = self._verify_one(envelope, tenant_id=tenant_id, now=now)
            if nonce in used_nonces or original["event_sha256"] in used_events:
                raise OwnerSignatureHold("duplicate_signed_nonce_or_event")
            used_nonces.add(nonce)
            used_events.add(original["event_sha256"])
            verified.append(original)
        research = review_prime_universal_evidence(
            tenant_id=tenant_id, as_of=now,
            original_owner_summaries=verified,
        )
        if (research["rejected_count"] or research["conflicting_event_count"]
            or research["cross_entity_link_violation_count"]
            or research["temporal_link_violation_count"]):
            raise OwnerSignatureHold("signed_batch_unexpected_fusion_rejections")
        founder = summarize_prime_founder_evidence(research)
        return {
            "schema_version": SCHEMA,
            "mode": "OBSERVE",
            "status": (
                "SIGNATURE_AND_OWNER_LOOKUP_SHADOW_PASS_REPLAY_GATE_HELD"
                if verified else "NO_SIGNED_SOURCE_INPUT_NOT_VERIFIED_ZERO"
            ),
            "submitted_count": len(signed_envelopes),
            "signature_and_owner_callback_preflight_count": len(verified),
            "founder_aggregate": founder,
            "source_custody_verified_in_production": False,
            "authenticated_issuer_configuration_verified_in_production": False,
            "replay_ledger_durable_and_atomic": False,
            "source_owner_consent_and_erasure_verified": False,
            "buyer_intent_independently_verified": False,
            "revenue_verified": False,
            "prediction_accuracy_verified": False,
            "source_admission_authorized": False,
            "production_integration_authorized": False,
            "astra_dispatched": False,
            "empiredb_written": False,
            "outbound_sent": False,
            "trades_executed": False,
            "execution_authority": "none",
            "blockers": [
                "INDEPENDENT_PRODUCTION_OWNER_KEY_PROVISIONING_REQUIRED",
                "ATOMIC_DURABLE_NONCE_REPLAY_LEDGER_NOT_CONNECTED",
                "AUTHORITATIVE_SOURCE_AND_BINDING_READERS_NOT_CONNECTED",
                "ORIGINAL_OWNER_SECURITY_RELEASE_REQUIRED",
            ],
        }
