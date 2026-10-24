"""EmpireOS Predictive Cloud V4.7: owner-signed source-admission shadow proof.

NOT a production trust registry. Two independent ED25519 owners must attest an
identical canonical scoped event. The roots and canonical state must arrive via
separate trusted channels; never accept public keys from an incoming envelope.
Even fully valid fictional fixture proof NEVER authorises Redis or execution.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SCHEMA = "empire.predictive_cloud.v47.owner_admission_fixture.v1"
PURPOSE = "PRIVATE_PREDICTIVE_RESEARCH_ONLY"
HEX64 = re.compile(r"^[a-f0-9]{64}$")
HEX128 = re.compile(r"^[a-f0-9]{128}$")
KEY_ID = re.compile(r"^[a-z][a-z0-9_-]{3,31}$")
SECTORS = frozenset({"roofing", "hvac", "solar", "dental", "legal", "b2b_saas",
                     "ecommerce", "logistics", "heat_pumps", "storm"})
CLAIM_FIELDS = frozenset({
    "schema_version", "tenant_id", "sector", "entity_digest",
    "source_evidence_digest", "event_digest", "revision", "event_kind",
    "permitted_purpose", "issued_at", "expires_at", "nonce_digest",
})
ENVELOPE_FIELDS = frozenset({
    "claim", "source_key_id", "tenant_key_id",
    "source_signature_hex", "tenant_signature_hex",
})
CANONICAL_FIELDS = frozenset({
    "tenant_id", "sector", "entity_digest", "source_evidence_digest",
    "event_digest", "revision", "event_kind", "latest_revision",
    "withdrawn", "source_review_state", "delivery_state", "execution_authority",
})


class V47AdmissionHold(ValueError):
    pass


@dataclass(frozen=True)
class FixtureTrustRoots:
    # Supplied by a separate trusted fixture owner, NEVER caller JSON.
    source_keys: dict[str, bytes]
    tenant_keys: dict[str, bytes]


@dataclass(frozen=True)
class FixtureRevocations:
    # In real operation this MUST be read from canonical DB by approved role.
    source_digests: frozenset[str] = frozenset()
    event_digests: frozenset[str] = frozenset()
    key_ids: frozenset[str] = frozenset()


def _hex(value: object, field: str, pattern=HEX64) -> str:
    if type(value) is not str or not pattern.fullmatch(value):
        raise V47AdmissionHold("invalid_" + field)
    return value


def _uuid(value: object) -> str:
    if type(value) is not str:
        raise V47AdmissionHold("canonical_tenant_uuid_required")
    try:
        parsed = UUID(value)
    except ValueError:
        raise V47AdmissionHold("canonical_tenant_uuid_required") from None
    if str(parsed) != value or parsed.int == 0:
        raise V47AdmissionHold("canonical_tenant_uuid_required")
    return value


def _stamp(value: object) -> datetime:
    if type(value) is not str or not 20 <= len(value) <= 40:
        raise V47AdmissionHold("exact_utc_stamp_required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise V47AdmissionHold("invalid_timestamp") from None
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise V47AdmissionHold("exact_utc_stamp_required")
    return parsed.astimezone(timezone.utc)


def _canonical_bytes(claim: dict) -> bytes:
    # Domain separation prevents a valid unrelated signature being reused.
    return (SCHEMA + "\n" + json.dumps(
        claim, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    )).encode("utf-8")


def _verify_signature(message: bytes, key_id: str, signature: object,
                      keys: dict[str, bytes], owner: str) -> bytes:
    if type(key_id) is not str or not KEY_ID.fullmatch(key_id):
        raise V47AdmissionHold("invalid_" + owner + "_key_id")
    _hex(signature, owner + "_signature", HEX128)
    if type(keys) is not dict or key_id not in keys or type(keys[key_id]) is not bytes:
        raise V47AdmissionHold("untrusted_" + owner + "_signer")
    raw = keys[key_id]
    if len(raw) != 32:
        raise V47AdmissionHold("invalid_" + owner + "_public_key")
    try:
        Ed25519PublicKey.from_public_bytes(raw).verify(bytes.fromhex(signature), message)
    except (ValueError, InvalidSignature):
        raise V47AdmissionHold("invalid_" + owner + "_signature") from None
    return raw


def review_signed_source_fixture(
    envelope: object,
    *,
    expected_tenant_id: str,
    canonical_row: object,
    trust_roots: FixtureTrustRoots,
    revocations: FixtureRevocations,
    now: datetime,
) -> dict[str, object]:
    """Verify detached owner proofs AND matching independent canonical row.

    This is restricted to test fixtures. Inputs named trust_roots, canonical_row,
    and revocations are only trustworthy when obtained independently. No
    production connector, credential, live verification, publishing or delivery.
    """
    tenant = _uuid(expected_tenant_id)
    if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
        raise V47AdmissionHold("trusted_aware_clock_required")
    clock = now.astimezone(timezone.utc)
    if type(trust_roots) is not FixtureTrustRoots or type(revocations) is not FixtureRevocations:
        raise V47AdmissionHold("independent_fixture_trust_required")
    if type(envelope) is not dict or set(envelope) != ENVELOPE_FIELDS:
        raise V47AdmissionHold("exact_signed_envelope_required")
    claim = envelope["claim"]
    if type(claim) is not dict or set(claim) != CLAIM_FIELDS:
        raise V47AdmissionHold("exact_canonical_claim_required")
    if claim["schema_version"] != SCHEMA:
        raise V47AdmissionHold("wrong_signature_domain")
    if _uuid(claim["tenant_id"]) != tenant:
        raise V47AdmissionHold("cross_tenant_claim_refused")
    if type(claim["sector"]) is not str or claim["sector"] not in SECTORS:
        raise V47AdmissionHold("unsupported_sector")
    for name in ("entity_digest", "source_evidence_digest", "event_digest", "nonce_digest"):
        _hex(claim[name], name)
    if type(claim["revision"]) is not int or not 1 <= claim["revision"] <= 1_000_000_000:
        raise V47AdmissionHold("invalid_source_revision")
    if claim["event_kind"] not in ("OBSERVED", "WITHDRAWN"):
        raise V47AdmissionHold("unsupported_event_kind")
    if claim["permitted_purpose"] != PURPOSE:
        raise V47AdmissionHold("cross_purpose_claim_refused")
    issued = _stamp(claim["issued_at"])
    expires = _stamp(claim["expires_at"])
    if not (issued <= clock < expires <= issued + timedelta(minutes=15)
            and clock - issued <= timedelta(minutes=5)):
        raise V47AdmissionHold("stale_future_or_expired_owner_claim")
    if (
        claim["source_evidence_digest"] in revocations.source_digests
        or claim["event_digest"] in revocations.event_digests
        or envelope["source_key_id"] in revocations.key_ids
        or envelope["tenant_key_id"] in revocations.key_ids
    ):
        raise V47AdmissionHold("owner_or_source_revoked")
    if envelope["source_key_id"] == envelope["tenant_key_id"]:
        raise V47AdmissionHold("independent_owner_keys_required")
    message = _canonical_bytes(claim)
    source_key = _verify_signature(
        message, envelope["source_key_id"], envelope["source_signature_hex"],
        trust_roots.source_keys, "source",
    )
    tenant_key = _verify_signature(
        message, envelope["tenant_key_id"], envelope["tenant_signature_hex"],
        trust_roots.tenant_keys, "tenant",
    )
    if source_key == tenant_key:
        raise V47AdmissionHold("independent_owner_keys_required")
    if type(canonical_row) is not dict or set(canonical_row) != CANONICAL_FIELDS:
        raise V47AdmissionHold("exact_owner_readback_required")
    for name in (
        "tenant_id", "sector", "entity_digest", "source_evidence_digest",
        "event_digest", "revision", "event_kind",
    ):
        if canonical_row[name] != claim[name] or type(canonical_row[name]) is not type(claim[name]):
            raise V47AdmissionHold("canonical_event_binding_mismatch")
    if type(canonical_row["latest_revision"]) is not int:
        raise V47AdmissionHold("invalid_durable_watermark")
    if canonical_row["latest_revision"] != claim["revision"]:
        raise V47AdmissionHold("stale_canonical_revision")
    if type(canonical_row["withdrawn"]) is not bool:
        raise V47AdmissionHold("invalid_withdrawal_record")
    if canonical_row["withdrawn"] or claim["event_kind"] == "WITHDRAWN":
        raise V47AdmissionHold("source_withdrawn")
    if (canonical_row["source_review_state"] != "UNVERIFIED"
        or canonical_row["delivery_state"] != "HELD"
        or canonical_row["execution_authority"] != "none"):
        raise V47AdmissionHold("owner_held_contract_not_verified")
    return {
        "schema_version": SCHEMA,
        "status": "FICTIONAL_DUAL_SIGNATURE_HELD_REVIEW",
        "tenant_id": tenant,
        "event_digest": claim["event_digest"],
        "canonical_revision_matched": True,
        "fixture_dual_signature_valid": True,
        "fixture_revocation_list_checked": True,
        "fixture_purpose_scoped": True,
        "live_trust_roots_attested": False,
        "real_source_rights_independently_verified": False,
        "real_crm_membership_verified": False,
        "production_source_admitted": False,
        "redis_publish_authorized": False,
        "execution_authority": "none",
        "recognized_revenue_cents": None,
    }
