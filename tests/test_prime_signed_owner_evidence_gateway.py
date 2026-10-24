"""Offline adversarial trials of original PRIME Ed25519 owner review boundary."""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from empire_os.prime_signed_owner_evidence_gateway import (
    AUDIENCE, SCOPE, SIGNED_SCHEMA, _canonical, OwnerSignatureHold,
    PrimeOwnerSignatureVerifier,
)
from empire_os.prime_universal_evidence_fusion import (
    APPROVED_PURPOSE, RECEIPT_SCHEMA,
)

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
TENANT = "tenant-original-fake"


def h(s):
    return sha256(s.encode()).hexdigest()


def receipt(owner="buyer_acquisition", klass="EXPLICIT_ENQUIRY", label="first"):
    return {
        "schema_version": RECEIPT_SCHEMA,
        "owner": owner, "evidence_class": klass,
        "event_sha256": h("event-" + label),
        "origin_sha256": h("origin-" + label),
        "entity_sha256": h("entity-" + label),
        "source_sha256": h("source-" + label),
        "tenant_scope_sha256": h(TENANT),
        "tenant_binding_sha256": h("canonical-binding-" + label),
        "observed_at": (NOW - timedelta(seconds=42)).isoformat(),
        "received_at": (NOW - timedelta(seconds=30)).isoformat(),
        "provenance_status": "ORIGINAL_OWNER_CUSTODY_REVIEWED",
        "source_rights_status": "OWNER_REVIEWED_PERMITTED",
        "permitted_purpose": APPROVED_PURPOSE,
        "supports_sha256": [],
        "contradicts_sha256": [],
        "prediction_as_of": None,
        "execution_authority": "none",
    }


def signer_pair():
    key = Ed25519PrivateKey.generate()  # ephemeral offline test only
    public = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return key, public


def verifier(pub, *,
             active=lambda owner, tenant, scope: True,
             bind=lambda tenant, entity, binding, as_of: True,
             custody=lambda owner, tenant, source, origin, event, as_of: True,
             owner="buyer_acquisition"):
    return PrimeOwnerSignatureVerifier(
        trusted_owner_public_keys={"original-key-test": (owner, pub)},
        owner_scope_active=active,
        canonical_binding_current=bind,
        source_custody_current=custody,
    )


def seal(key, *, row=None, **overrides):
    row = receipt() if row is None else row
    payload = {
        "schema_version": SIGNED_SCHEMA, "audience": AUDIENCE,
        "scope": SCOPE, "issuer_owner": row["owner"],
        "tenant_scope_sha256": h(TENANT),
        "issued_at": (NOW - timedelta(minutes=1)).isoformat(),
        "expires_at": (NOW + timedelta(minutes=2)).isoformat(),
        "nonce": "long-test-nonce-unique-value-01",
        "receipt": row,
    }
    payload.update(overrides)
    encoded = base64.urlsafe_b64encode(
        key.sign(_canonical(payload))
    ).rstrip(b"=").decode("ascii")
    return {"kid": "original-key-test", "payload": payload, "signature": encoded}


def go(v, *env):
    return v.review(tenant_id=TENANT, as_of=NOW, signed_envelopes=list(env))


def test_offline_signed_verified_owner_preflight_never_activates_live_feed():
    private, public = signer_pair()
    report = go(verifier(public), seal(private))
    assert report["signature_and_owner_callback_preflight_count"] == 1
    assert report["status"] == "SIGNATURE_AND_OWNER_LOOKUP_SHADOW_PASS_REPLAY_GATE_HELD"
    assert report["source_admission_authorized"] is False
    assert report["replay_ledger_durable_and_atomic"] is False
    assert report["authenticated_issuer_configuration_verified_in_production"] is False
    assert report["empiredb_written"] is False
    assert report["outbound_sent"] is False
    assert report["trades_executed"] is False
    assert report["execution_authority"] == "none"
    founder = report["founder_aggregate"]
    assert founder["accepted_record_count_band"] == "0-4"
    assert "group_reviews" not in founder
    assert h(TENANT) not in str(report)
    assert h("entity-first") not in str(report)


@pytest.mark.parametrize("change,reason", [
    ({"kid": "other-key"}, "unknown_or_malformed"),
    ({"signature": "x" * 86}, "invalid"),
    ({"signature": ""}, "invalid"),
    ({"payload": {"different": "payload"}}, "exact_original"),
])
def test_malformed_or_unknown_signer_rejected(change, reason):
    private, public = signer_pair()
    envelope = seal(private)
    envelope.update(change)
    with pytest.raises(OwnerSignatureHold, match=reason):
        go(verifier(public), envelope)


@pytest.mark.parametrize("change,reason", [
    ({"audience": "empire-revenue-crm"}, "wrong_audience"),
    ({"scope": "outbound:send"}, "wrong_audience"),
    ({"issuer_owner": "economic_memory"}, "wrong_audience"),
    ({"tenant_scope_sha256": h("attacker")}, "wrong_audience"),
    ({"issued_at": (NOW + timedelta(seconds=1)).isoformat()}, "expired_or_future"),
    ({"expires_at": (NOW - timedelta(seconds=1)).isoformat()}, "expired_or_future"),
    ({"expires_at": (NOW + timedelta(hours=1)).isoformat()}, "expired_or_future"),
    ({"nonce": "weak"}, "signed_nonce"),
])
def test_valid_signature_but_wrong_audience_scope_time_tenant_or_nonce(change, reason):
    private, public = signer_pair()
    with pytest.raises(OwnerSignatureHold, match=reason):
        go(verifier(public), seal(private, **change))


def test_malicious_signed_receipt_cannot_create_revenue_or_sender_authority():
    private, public = signer_pair()
    row = receipt()
    row["evidence_class"] = "REALIZED_OUTCOME"
    with pytest.raises(OwnerSignatureHold, match="original_evidence_contract"):
        go(verifier(public), seal(private, row=row))
    row = receipt()
    row["execution_authority"] = "outbound"
    with pytest.raises(OwnerSignatureHold, match="original_evidence_contract"):
        go(verifier(public), seal(private, row=row))


def test_signature_tamper_rejected_and_not_trusted_from_payload_public_keys():
    private, public = signer_pair()
    env = seal(private)
    env["payload"]["receipt"]["source_sha256"] = h("tampered")
    with pytest.raises(OwnerSignatureHold, match="signature_invalid"):
        go(verifier(public), env)
    env = seal(private)
    env["public_key"] = public.hex()
    with pytest.raises(OwnerSignatureHold, match="unknown_or_malformed"):
        go(verifier(public), env)


@pytest.mark.parametrize("denial,reason", [
    ("scope", "scope_not_active"),
    ("binding", "binding_unverified"),
    ("custody", "custody_unverified"),
])
def test_independent_original_owner_boundaries_must_each_agree(denial, reason):
    private, public = signer_pair()
    kwargs = {
        "active": (lambda *args: denial != "scope"),
        "bind": (lambda *args: denial != "binding"),
        "custody": (lambda *args: denial != "custody"),
    }
    with pytest.raises(OwnerSignatureHold, match=reason):
        go(verifier(public, **kwargs), seal(private))


def test_callback_failure_held_and_no_default_permissions():
    private, public = signer_pair()
    def unavailable(*_):
        raise ConnectionError("private-provider-internal-record-123")
    with pytest.raises(OwnerSignatureHold, match="reader_unavailable") as exc:
        go(verifier(public, custody=unavailable), seal(private))
    assert "private-provider-internal" not in str(exc.value)
    with pytest.raises(OwnerSignatureHold, match="dependencies_required"):
        PrimeOwnerSignatureVerifier(
            trusted_owner_public_keys={"original-key-test": ("buyer_acquisition", public)},
            owner_scope_active=None,
            canonical_binding_current=lambda *_: True,
            source_custody_current=lambda *_: True,
        )


def test_no_live_cryptographic_issuer_provisioning_is_claimed():
    private, public = signer_pair()
    assert go(verifier(public), seal(private))["source_custody_verified_in_production"] is False
    assert go(verifier(public), seal(private))["replay_ledger_durable_and_atomic"] is False


def test_duplicate_nonce_and_event_in_batch_rejected():
    private, public = signer_pair()
    a = seal(private)
    with pytest.raises(OwnerSignatureHold, match="duplicate"):
        go(verifier(public), a, dict(a))
    b = seal(private, row=receipt(label="second"))
    with pytest.raises(OwnerSignatureHold, match="duplicate"):
        go(verifier(public), a, b)


def test_different_nonce_but_same_event_rejected():
    private, public = signer_pair()
    a = seal(private)
    b = seal(private, nonce="different-unique-nonce-value-02")
    with pytest.raises(OwnerSignatureHold, match="duplicate"):
        go(verifier(public), a, b)


def test_multiple_distinct_signed_events_can_be_reviewed_without_source_reads():
    private, public = signer_pair()
    a = seal(private)
    b = seal(private, row=receipt(label="second"),
             nonce="another-different-nonce-value-02")
    result = go(verifier(public), a, b)
    assert result["submitted_count"] == 2
    assert result["founder_aggregate"]["accepted_record_count_band"] == "0-4"
    assert result["production_integration_authorized"] is False


def test_source_owner_mismatch_even_when_signed_is_held():
    private, public = signer_pair()
    row = receipt(owner="smart_crm")
    env = seal(private, row=row)
    with pytest.raises(OwnerSignatureHold, match="wrong_audience"):
        go(verifier(public), env)


def test_missing_customer_custody_is_a_real_hold_even_with_valid_signature():
    private, public = signer_pair()
    with pytest.raises(OwnerSignatureHold, match="custody_unverified"):
        go(verifier(public, custody=lambda *_: None), seal(private))


def test_pinned_trusted_key_cannot_be_swapped_using_an_attacker_key():
    original_private, original_public = signer_pair()
    attacker, _attacker_public = signer_pair()
    with pytest.raises(OwnerSignatureHold, match="signature_invalid"):
        go(verifier(original_public), seal(attacker))


def test_empty_batch_is_not_a_real_owner_authentication_event():
    private, public = signer_pair()
    result = go(verifier(public))
    assert result["signature_and_owner_callback_preflight_count"] == 0
    assert result["source_admission_authorized"] is False
    assert result["founder_aggregate"]["source_connection_status"] == "OWNER_INPUT_UNAUTHENTICATED"


def test_canonical_unsafe_inputs_fail_without_exporting_details():
    private, public = signer_pair()
    row = receipt()
    row["raw_email"] = "someone-private@example.com"
    with pytest.raises(OwnerSignatureHold, match="original_evidence_contract") as err:
        go(verifier(public), seal(private, row=row))
    assert "someone-private" not in str(err.value)
    with pytest.raises(OwnerSignatureHold, match="bounded_original_owner"):
        go(verifier(public), *[seal(private, row=receipt(label=str(i)),
                nonce=f"offline-test-nonce-for-{i:04d}-unique")
                for i in range(101)])


def test_signed_research_input_is_optional_in_original_predictive_bridge():
    from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review
    private, public = signer_pair()
    result = build_predictive_revenue_brain_review(
        tenant_id=TENANT, as_of=NOW,
        signed_owner_evidence_envelopes=[seal(private)],
        original_owner_signature_verifier=verifier(public),
    )
    assert result["prime_signed_owner_preflight_status"] == (
        "SIGNATURE_AND_OWNER_LOOKUP_SHADOW_PASS_REPLAY_GATE_HELD"
    )
    assert result["prime_signed_owner_replay_protection_verified"] is False
    assert result["prime_universal_evidence_shadow"]["small_cells_suppressed"] is True
    assert result["astra_dispatch_executed"] is False
    assert result["forecast_model_promoted"] is False
    assert result["recognized_revenue_cents"] is None
    assert result["database_writes"] is False
    assert "group_reviews" not in str(result["prime_universal_evidence_shadow"])


def test_signed_and_unsigned_inputs_cannot_be_mixed_or_bypass_verifier():
    from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review
    private, public = signer_pair()
    with pytest.raises(ValueError, match="mixed_original"):
        build_predictive_revenue_brain_review(
            tenant_id=TENANT, as_of=NOW,
            original_owner_evidence_summaries=[receipt()],
            signed_owner_evidence_envelopes=[seal(private)],
            original_owner_signature_verifier=verifier(public),
        )
    with pytest.raises(ValueError, match="trusted_original"):
        build_predictive_revenue_brain_review(
            tenant_id=TENANT, as_of=NOW,
            signed_owner_evidence_envelopes=[seal(private)],
        )
    with pytest.raises(ValueError, match="without_signed"):
        build_predictive_revenue_brain_review(
            tenant_id=TENANT, as_of=NOW,
            original_owner_signature_verifier=verifier(public),
        )


def test_empty_signed_input_preserves_unverified_zero_status():
    private, public = signer_pair()
    r = go(verifier(public))
    assert r["status"] == "NO_SIGNED_SOURCE_INPUT_NOT_VERIFIED_ZERO"
    assert r["source_admission_authorized"] is False


def test_signed_path_cannot_use_fake_financial_or_buyer_source_claim():
    from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review
    private, public = signer_pair()
    invalid = receipt()
    invalid["evidence_class"] = "REALIZED_OUTCOME"
    with pytest.raises(OwnerSignatureHold, match="original_evidence_contract"):
        build_predictive_revenue_brain_review(
            tenant_id=TENANT, as_of=NOW,
            signed_owner_evidence_envelopes=[seal(private, row=invalid)],
            original_owner_signature_verifier=verifier(public),
        )


def test_same_valid_signature_could_replay_across_batches_so_live_admission_stays_held():
    private, public = signer_pair()
    single_envelope = seal(private)
    trusted_shadow_verifier = verifier(public)
    first = go(trusted_shadow_verifier, single_envelope)
    repeated = go(trusted_shadow_verifier, single_envelope)
    assert first["status"] == repeated["status"]
    assert first["replay_ledger_durable_and_atomic"] is False
    assert repeated["source_admission_authorized"] is False
    assert "ATOMIC_DURABLE_NONCE_REPLAY_LEDGER_NOT_CONNECTED" in repeated["blockers"]
