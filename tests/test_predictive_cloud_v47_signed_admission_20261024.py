"""V4.7 fictional dual-Ed25519 source+tenant admission shadow acceptance."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from empire_os.predictive_cloud_v47_admission_shadow import (
    SCHEMA, PURPOSE, FixtureTrustRoots, FixtureRevocations, V47AdmissionHold,
    _canonical_bytes, review_signed_source_fixture,
)

NOW = datetime(2026, 10, 24, 20, 0, tzinfo=timezone.utc)
TENANT = "00000000-0000-0000-0000-000000000101"
OTHER = "00000000-0000-0000-0000-000000000102"


def digest(label):
    return sha256(("fictional-empire-v47:" + label).encode()).hexdigest()


def fixture():
    source = Ed25519PrivateKey.generate()
    tenant = Ed25519PrivateKey.generate()
    public = lambda key: key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    claim = {
        "schema_version": SCHEMA,
        "tenant_id": TENANT,
        "sector": "roofing",
        "entity_digest": digest("entity"),
        "source_evidence_digest": digest("source"),
        "event_digest": digest("event-11"),
        "revision": 11,
        "event_kind": "OBSERVED",
        "permitted_purpose": PURPOSE,
        "issued_at": (NOW - timedelta(seconds=20)).isoformat(),
        "expires_at": (NOW + timedelta(minutes=8)).isoformat(),
        "nonce_digest": digest("nonce-11"),
    }
    data = _canonical_bytes(claim)
    envelope = {
        "claim": claim,
        "source_key_id": "source_fixture_v47",
        "tenant_key_id": "tenant_fixture_v47",
        "source_signature_hex": source.sign(data).hex(),
        "tenant_signature_hex": tenant.sign(data).hex(),
    }
    roots = FixtureTrustRoots(
        source_keys={"source_fixture_v47": public(source)},
        tenant_keys={"tenant_fixture_v47": public(tenant)},
    )
    canonical = {
        "tenant_id": TENANT, "sector": "roofing",
        "entity_digest": claim["entity_digest"],
        "source_evidence_digest": claim["source_evidence_digest"],
        "event_digest": claim["event_digest"],
        "revision": 11, "event_kind": "OBSERVED",
        "latest_revision": 11, "withdrawn": False,
        "source_review_state": "UNVERIFIED",
        "delivery_state": "HELD", "execution_authority": "none",
    }
    return envelope, roots, canonical


def reviewed(envelope=None, roots=None, canonical=None, revocations=None, now=NOW):
    default_envelope, default_roots, default_canonical = fixture()
    return review_signed_source_fixture(
        default_envelope if envelope is None else envelope,
        trust_roots=default_roots if roots is None else roots,
        canonical_row=default_canonical if canonical is None else canonical,
        revocations=FixtureRevocations() if revocations is None else revocations,
        expected_tenant_id=TENANT, now=now,
    )


def check(envelope, roots, canonical, **overrides):
    return review_signed_source_fixture(
        envelope, expected_tenant_id=overrides.get("tenant", TENANT),
        canonical_row=canonical,
        trust_roots=roots, revocations=overrides.get("revocations", FixtureRevocations()),
        now=overrides.get("now", NOW),
    )


def test_valid_independent_signatures_still_do_not_grant_production_authority():
    envelope, roots, canonical = fixture()
    r = check(envelope, roots, canonical)
    assert r["fixture_dual_signature_valid"] is True
    assert r["canonical_revision_matched"] is True
    assert r["production_source_admitted"] is False
    assert r["redis_publish_authorized"] is False
    assert r["real_crm_membership_verified"] is False
    assert r["live_trust_roots_attested"] is False
    assert r["recognized_revenue_cents"] is None


@pytest.mark.parametrize("field,value,reason", [
    ("tenant_id", OTHER, "cross_tenant_claim_refused"),
    ("sector", "other", "unsupported_sector"),
    ("entity_digest", "2" * 63, "invalid_entity_digest"),
    ("source_evidence_digest", "raw email@example.com", "invalid_source_evidence_digest"),
    ("event_digest", "d" * 63, "invalid_event_digest"),
    ("revision", True, "invalid_source_revision"),
    ("revision", 0, "invalid_source_revision"),
    ("event_kind", "PAID", "unsupported_event_kind"),
    ("permitted_purpose", "MARKETING_CONTACT", "cross_purpose_claim_refused"),
    ("schema_version", "untrusted-v1", "wrong_signature_domain"),
    ("issued_at", "2026-10-24T22:00:00", "exact_utc_stamp_required"),
    ("expires_at", "2026-10-24T10:00:00+00:00", "stale_future_or_expired_owner_claim"),
    ("nonce_digest", "bad", "invalid_nonce_digest"),
])
def test_unsigned_claim_mutation_cannot_cross_boundary(field, value, reason):
    envelope, roots, canonical = fixture()
    envelope["claim"][field] = value
    with pytest.raises(V47AdmissionHold, match=reason):
        check(envelope, roots, canonical)


@pytest.mark.parametrize("field,value,reason", [
    ("source_signature_hex", "0" * 128, "invalid_source_signature"),
    ("tenant_signature_hex", "0" * 128, "invalid_tenant_signature"),
    ("source_key_id", "unknown_signer", "untrusted_source_signer"),
    ("tenant_key_id", "unknown_signer", "untrusted_tenant_signer"),
])
def test_forged_or_unknown_owner_signature_rejected(field, value, reason):
    envelope, roots, canonical = fixture()
    envelope[field] = value
    with pytest.raises(V47AdmissionHold, match=reason):
        check(envelope, roots, canonical)


@pytest.mark.parametrize("field,value,reason", [
    ("tenant_id", OTHER, "canonical_event_binding_mismatch"),
    ("revision", 12, "canonical_event_binding_mismatch"),
    ("source_evidence_digest", "f" * 64, "canonical_event_binding_mismatch"),
    ("event_digest", "f" * 64, "canonical_event_binding_mismatch"),
    ("latest_revision", 12, "stale_canonical_revision"),
    ("withdrawn", True, "source_withdrawn"),
    ("source_review_state", "VERIFIED", "owner_held_contract_not_verified"),
    ("delivery_state", "SENT", "owner_held_contract_not_verified"),
    ("execution_authority", "publish", "owner_held_contract_not_verified"),
])
def test_independently_read_canonical_owner_record_is_mandatory(field, value, reason):
    envelope, roots, canonical = fixture()
    canonical[field] = value
    with pytest.raises(V47AdmissionHold, match=reason):
        check(envelope, roots, canonical)


def test_distinct_signer_roles_cannot_share_key():
    envelope, roots, canonical = fixture()
    fake = FixtureTrustRoots(source_keys=roots.source_keys,
                             tenant_keys={"tenant_fixture_v47": next(iter(roots.source_keys.values()))})
    with pytest.raises(V47AdmissionHold, match="invalid_tenant_signature"):
        check(envelope, fake, canonical)


@pytest.mark.parametrize("scope", ["source_digests", "event_digests", "key_ids"])
def test_independently_supplied_revocations_refuse_even_valid_signatures(scope):
    envelope, roots, canonical = fixture()
    value = (envelope["claim"]["source_evidence_digest"]
             if scope == "source_digests" else
             envelope["claim"]["event_digest"]
             if scope == "event_digests" else
             envelope["source_key_id"])
    revoked = FixtureRevocations(**{scope: frozenset([value])})
    with pytest.raises(V47AdmissionHold, match="owner_or_source_revoked"):
        check(envelope, roots, canonical, revocations=revoked)


def test_expiry_rejected_against_independent_clock():
    envelope, roots, canonical = fixture()
    with pytest.raises(V47AdmissionHold, match="stale_future_or_expired_owner_claim"):
        check(envelope, roots, canonical, now=NOW + timedelta(hours=1))


def test_extra_claim_key_and_untrusted_embedded_root_both_rejected():
    envelope, roots, canonical = fixture()
    envelope["tenant_public_key"] = "a" * 64
    with pytest.raises(V47AdmissionHold, match="exact_signed_envelope_required"):
        check(envelope, roots, canonical)
    envelope.pop("tenant_public_key")
    envelope["claim"]["execution_authority"] = "none"
    with pytest.raises(V47AdmissionHold, match="exact_canonical_claim_required"):
        check(envelope, roots, canonical)


def test_claim_signed_by_wrong_source_role_is_rejected():
    envelope, roots, canonical = fixture()
    # Swapping known IDs and signatures cannot turn a CRM signature into rights.
    envelope["source_key_id"] = "tenant_fixture_v47"
    envelope["source_signature_hex"] = envelope["tenant_signature_hex"]
    with pytest.raises(V47AdmissionHold, match="independent_owner_keys_required"):
        check(envelope, roots, canonical)


def test_missing_independent_canonical_row_fails_closed():
    envelope, roots, canonical = fixture()
    with pytest.raises(V47AdmissionHold, match="exact_owner_readback_required"):
        check(envelope, roots, None)
