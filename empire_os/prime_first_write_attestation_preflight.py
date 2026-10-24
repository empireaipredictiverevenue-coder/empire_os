"""PRIME first-write journal attestation preflight; original owners only.

Follows original EmpireOS pinned Ed25519 verification pattern. Proof requires
original Security/EmpireDB authority over an append-only first-write record.
This pure verifier does NOT provision keys, write a journal, reserve nonces,
establish the real first write, authenticate underlying finance or release data.
"""
from __future__ import annotations

import base64
import binascii
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from empire_os.prime_forward_prediction_journal import (
    MAX_PREDICTIONS, _prediction, _text, _time,
)
from empire_os.prime_universal_evidence_fusion import _digest

SCHEMA = "empire.prime.first_write_attestation_preflight.v1"
SIGNED_SCHEMA = "empire.prime.original_first_write_attestation.v1"
DOMAIN = b"empire-prime-original-first-write-ed25519-v1:"
AUDIENCE = "empire-prime-forward-journal-observe"
SCOPE = "predictive:original-journal:first-write-review"
RECORD_FIELDS = frozenset({
    "prediction_ref", "tenant_scope_sha256", "prediction_sha256",
    "first_written_at", "source_record_sha256", "journal_owner",
    "schema_version", "audience", "scope", "issued_at", "expires_at", "nonce",
})
ENVELOPE_FIELDS = frozenset({"kid", "payload", "signature"})
READBACK_FIELDS = frozenset({
    "prediction_ref", "tenant_scope_sha256", "prediction_sha256",
    "first_written_at", "source_record_sha256",
    "append_only_uniqueness_verified",
})
ID = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
NONCE = re.compile(r"^[A-Za-z0-9_-]{24,96}$")
HEX = re.compile(r"^[a-f0-9]{64}$")
MAX_TTL = timedelta(minutes=10)
EXPECTED_OWNER = "predictive_cloud"


class PrimeFirstWriteHold(ValueError):
    """Original journal first-write attestation is unverified or unsafe."""


def _canonical(obj: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(obj), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def prediction_digest(row: Mapping[str, Any], *, tenant_id: str, as_of: datetime) -> str:
    """Opaque digest of exact owner-submitted, validated original prediction."""
    parsed = _prediction(row, _text(tenant_id, "tenant"), as_of)
    return sha256(b"empire-prime-forward-prediction-v1:" + _canonical(parsed)).hexdigest()


def _signature(sig: Any) -> bytes:
    if type(sig) is not str or len(sig) != 86 or not re.fullmatch(r"[A-Za-z0-9_-]{86}", sig):
        raise PrimeFirstWriteHold("canonical_Ed25519_signature_required")
    try:
        raw = base64.b64decode(sig + "==", altchars=b"-_", validate=True)
    except (binascii.Error, ValueError):
        raise PrimeFirstWriteHold("canonical_Ed25519_signature_required") from None
    if len(raw) != 64 or base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii") != sig:
        raise PrimeFirstWriteHold("canonical_Ed25519_signature_required")
    return raw


class PrimeOriginalFirstWriteVerifier:
    """Offline signer/readback consistency preflight, never production proof.

    The caller cannot replace the independently configured pinned signer or
    original owner readback with an envelope field. Trusted callbacks and keys
    must only be wired by the original Core, Security and EmpireDB owners.
    """

    def __init__(
        self, *, trusted_first_write_public_keys: Mapping[str, bytes],
        active_journal_authority: Callable[[str, str, datetime], bool],
        read_canonical_first_write: Callable[[str, str, datetime], Mapping[str, Any] | None],
    ) -> None:
        if (type(trusted_first_write_public_keys) is not dict
            or not 1 <= len(trusted_first_write_public_keys) <= 20
            or not callable(active_journal_authority)
            or not callable(read_canonical_first_write)):
            raise PrimeFirstWriteHold("original_first_write_owner_dependencies_required")
        keys: dict[str, Ed25519PublicKey] = {}
        for kid, material in trusted_first_write_public_keys.items():
            if (type(kid) is not str or not ID.fullmatch(kid)
                or type(material) is not bytes or len(material) != 32):
                raise PrimeFirstWriteHold("invalid_pinned_original_first_write_key")
            try:
                keys[kid] = Ed25519PublicKey.from_public_bytes(material)
            except ValueError:
                raise PrimeFirstWriteHold("invalid_pinned_original_first_write_key") from None
        self._keys = keys
        self._authority = active_journal_authority
        self._readback = read_canonical_first_write

    def review(
        self, *, tenant_id: str, as_of: datetime,
        original_predictions: Sequence[Mapping[str, Any]],
        signed_attestations: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        if (type(original_predictions) not in (list, tuple)
            or type(signed_attestations) not in (list, tuple)
            or not 1 <= len(original_predictions) <= MAX_PREDICTIONS
            or len(original_predictions) != len(signed_attestations)):
            raise PrimeFirstWriteHold("exact_bounded_signed_prediction_cohort_required")
        tenant = _text(tenant_id, "tenant_id")
        if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
            raise PrimeFirstWriteHold("trusted_current_review_time_required")
        now = as_of.astimezone(timezone.utc)
        expected: dict[str, tuple[str, datetime]] = {}
        for row in original_predictions:
            try:
                validated = _prediction(row, tenant, now)
                digest = prediction_digest(validated, tenant_id=tenant, as_of=now)
            except ValueError:
                raise PrimeFirstWriteHold("invalid_original_prediction_contract") from None
            ref = validated["prediction_ref"]
            if ref in expected:
                raise PrimeFirstWriteHold("duplicate_original_prediction_reference")
            expected[ref] = (digest, _time(validated["journal_recorded_at"]))
        seen = set()
        nonce_set = set()
        source_record_set = set()
        for envelope in signed_attestations:
            if (type(envelope) is not dict or set(envelope) != ENVELOPE_FIELDS
                or type(envelope.get("kid")) is not str
                or envelope["kid"] not in self._keys
                or type(envelope.get("payload")) is not dict):
                raise PrimeFirstWriteHold("unknown_or_malformed_first_write_envelope")
            body = envelope["payload"]
            if set(body) != RECORD_FIELDS:
                raise PrimeFirstWriteHold("exact_first_write_signed_fields_required")
            if (body["schema_version"] != SIGNED_SCHEMA
                or body["audience"] != AUDIENCE or body["scope"] != SCOPE
                or body["journal_owner"] != EXPECTED_OWNER
                or body["tenant_scope_sha256"] != _digest(tenant)):
                raise PrimeFirstWriteHold("first_write_wrong_owner_scope_or_tenant")
            ref = body["prediction_ref"]
            if type(ref) is not str or ref not in expected:
                raise PrimeFirstWriteHold("signed_prediction_not_in_original_cohort")
            if ref in seen:
                raise PrimeFirstWriteHold("duplicate_signed_first_write_prediction")
            value = body["prediction_sha256"]
            record = body["source_record_sha256"]
            if (type(value) is not str or not HEX.fullmatch(value)
                or type(record) is not str or not HEX.fullmatch(record)
                or value != expected[ref][0]):
                raise PrimeFirstWriteHold("original_prediction_or_record_digest_mismatch")
            nonce = body["nonce"]
            if type(nonce) is not str or not NONCE.fullmatch(nonce) or nonce in nonce_set:
                raise PrimeFirstWriteHold("invalid_or_duplicate_first_write_nonce")
            first_write = _time(body["first_written_at"])
            issued = _time(body["issued_at"])
            expires = _time(body["expires_at"])
            # A first-write proof must have been signed in the original write
            # window. A newly signed historical row is hindsight, even when
            # the claimed journal timestamp was backdated. Archival review
            # may occur after the original short-lived issuance window.
            if (first_write != expected[ref][1]
                or not first_write <= issued <= first_write + timedelta(seconds=60)
                or issued > now
                or not issued < expires
                or expires - issued > MAX_TTL):
                raise PrimeFirstWriteHold("backdated_future_or_expired_first_write")
            try:
                self._keys[envelope["kid"]].verify(
                    _signature(envelope["signature"]), DOMAIN + _canonical(body),
                )
            except (InvalidSignature, ValueError, TypeError, OverflowError):
                raise PrimeFirstWriteHold("invalid_original_first_write_signature") from None
            try:
                active = self._authority(tenant, SCOPE, now) is True
                retrieved = self._readback(tenant, ref, now)
            except Exception:
                raise PrimeFirstWriteHold("original_first_write_reader_unavailable") from None
            if not active:
                raise PrimeFirstWriteHold("original_journal_owner_scope_inactive")
            if type(retrieved) is not dict or set(retrieved) != READBACK_FIELDS:
                raise PrimeFirstWriteHold("canonical_first_write_record_unavailable")
            if (retrieved["prediction_ref"] != ref
                or retrieved["tenant_scope_sha256"] != _digest(tenant)
                or retrieved["prediction_sha256"] != value
                or retrieved["source_record_sha256"] != record
                or _time(retrieved["first_written_at"]) != first_write
                or retrieved["append_only_uniqueness_verified"] is not True):
                raise PrimeFirstWriteHold("canonical_first_write_readback_conflict")
            if record in source_record_set:
                raise PrimeFirstWriteHold("duplicate_canonical_first_write_record_digest")
            seen.add(ref)
            nonce_set.add(nonce)
            source_record_set.add(record)
        if set(expected) != seen:
            raise PrimeFirstWriteHold("incomplete_original_signed_prediction_cohort")
        return {
            "schema_version": SCHEMA,
            "mode": "OBSERVE",
            "status": "OFFLINE_SIGNED_FIRST_WRITE_READBACK_PREFLIGHT_PASS_RELEASE_HELD",
            "owner_signed_reviewed_record_count": len(seen),
            "signed_payload_and_readback_equal_in_supplied_fixture": True,
            "source_issuer_live_key_provisioning_verified": False,
            "original_first_write_production_registry_authenticated": False,
            "first_write_external_timestamp_anchor_verified": False,
            "atomic_durable_nonce_replay_protection_verified": False,
            "append_only_immutability_independently_audited": False,
            "real_market_or_commercial_prediction_accuracy_verified": False,
            "original_model_version_promotion_authorized": False,
            "production_release_authorized": False,
            "database_writes": False,
            "astra_dispatched": False,
            "outbound_sent": False,
            "trading_executed": False,
            "execution_authority": "none",
            "blockers": [
                "ORIGINAL_SECURITY_PRODUCTION_ISSUER_KEYS_NOT_PROVISIONED",
                "ATOMIC_DURABLE_REPLAY_RESERVATION_NOT_DEPLOYED",
                "FIRST_WRITE_INDEPENDENT_TIMESTAMP_AND_APPEND_ONLY_AUDIT_REQUIRED",
                "ORIGINAL_DATABASE_AND_SOURCE_OWNER_RELEASE_NOT_APPROVED",
            ],
        }
