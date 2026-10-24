"""Original PRIME durable-first-write proof contract tests; offline keys ONLY."""
from __future__ import annotations

from copy import deepcopy
import base64
from datetime import timedelta
from hashlib import sha256

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
import pytest

from empire_os.prime_first_write_attestation_preflight import (
    PrimeOriginalFirstWriteVerifier, PrimeFirstWriteHold,
    SIGNED_SCHEMA, AUDIENCE, SCOPE, DOMAIN, _canonical, prediction_digest,
)
from test_prime_forward_prediction_journal import forecast, NOW, TENANT


def d(value):
    return sha256(value.encode("utf8")).hexdigest()


def keys():
    private = Ed25519PrivateKey.generate()  # transient tests, no deployed issuer
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw,
    )
    return private, public


def attest(private, row=None, **updates):
    row = forecast() if row is None else row
    first = row["journal_recorded_at"]
    from datetime import datetime
    moment = datetime.fromisoformat(first)
    body = {
        "schema_version": SIGNED_SCHEMA,
        "audience": AUDIENCE, "scope": SCOPE,
        "journal_owner": "predictive_cloud",
        "tenant_scope_sha256": d(TENANT),
        "prediction_ref": row["prediction_ref"],
        "prediction_sha256": prediction_digest(row, tenant_id=TENANT, as_of=NOW),
        "source_record_sha256": d("original-durable-first-write"),
        "first_written_at": first,
        "issued_at": (moment + timedelta(seconds=15)).isoformat(),
        "expires_at": (moment + timedelta(minutes=3)).isoformat(),
        "nonce": "offline-first-write-nonce-00001",
    }
    body.update(updates)
    sig = base64.urlsafe_b64encode(
        private.sign(DOMAIN + _canonical(body))
    ).rstrip(b"=").decode("ascii")
    return {"kid": "original-key-one", "payload": body, "signature": sig}


def verifier(public, *, authority=lambda *_: True, lookup=None):
    if lookup is None:
        def lookup(tenant, ref, when):
            return {
                "prediction_ref": ref,
                "tenant_scope_sha256": d(tenant),
                "prediction_sha256": prediction_digest(
                    forecast(), tenant_id=tenant, as_of=when
                ),
                "first_written_at": forecast()["journal_recorded_at"],
                "source_record_sha256": d("original-durable-first-write"),
                "append_only_uniqueness_verified": True,
            }
    return PrimeOriginalFirstWriteVerifier(
        trusted_first_write_public_keys={"original-key-one": public},
        active_journal_authority=authority,
        read_canonical_first_write=lookup,
    )


def review(v, *rows, envelopes):
    return v.review(tenant_id=TENANT, as_of=NOW, original_predictions=list(rows),
                    signed_attestations=list(envelopes))


def test_first_write_offline_signed_preflight_pass_does_not_create_authority():
    private, public = keys()
    x = review(verifier(public), forecast(), envelopes=[attest(private)])
    assert x["owner_signed_reviewed_record_count"] == 1
    assert x["signed_payload_and_readback_equal_in_supplied_fixture"] is True
    assert x["original_first_write_production_registry_authenticated"] is False
    assert x["first_write_external_timestamp_anchor_verified"] is False
    assert x["atomic_durable_nonce_replay_protection_verified"] is False
    assert x["production_release_authorized"] is False
    assert x["database_writes"] is False and x["outbound_sent"] is False
    assert x["execution_authority"] == "none"
    assert TENANT not in str(x)


def test_wrong_pinned_signature_rejected_even_when_readback_claims_true():
    original, public = keys()
    forged, _ = keys()
    with pytest.raises(PrimeFirstWriteHold, match="invalid_original_first_write_signature"):
        review(verifier(public), forecast(), envelopes=[attest(forged)])


def test_mutated_prediction_or_model_version_breaks_signature_digest():
    private, public = keys()
    changed = forecast(predicted_probability=0.7)
    with pytest.raises(PrimeFirstWriteHold, match="original_prediction_or_record_digest"):
        review(verifier(public), changed, envelopes=[attest(private)])
    changed = forecast(model_version_sha256=d("model-v2"))
    with pytest.raises(PrimeFirstWriteHold, match="original_prediction_or_record_digest"):
        review(verifier(public), changed, envelopes=[attest(private)])


@pytest.mark.parametrize("changes,reason", [
    ({"audience": "empire-crm"}, "wrong_owner_scope"),
    ({"scope": "outbound:send"}, "wrong_owner_scope"),
    ({"journal_owner": "fake-founder"}, "wrong_owner_scope"),
    ({"tenant_scope_sha256": d("other-tenant")}, "wrong_owner_scope"),
    ({"source_record_sha256": "untrusted raw string"}, "original_prediction_or_record_digest"),
    ({"issued_at": (NOW - timedelta(minutes=1)).isoformat()}, "backdated_future_or_expired"),
    ({"first_written_at": (NOW - timedelta(days=3)).isoformat()}, "backdated_future_or_expired"),
    ({"expires_at": (NOW + timedelta(minutes=30)).isoformat()}, "backdated_future_or_expired"),
    ({"nonce": "too-short"}, "invalid_or_duplicate"),
])
def test_correct_signature_cannot_expand_scope_or_backfill_history(changes, reason):
    private, public = keys()
    with pytest.raises(PrimeFirstWriteHold, match=reason):
        review(verifier(public), forecast(), envelopes=[attest(private, **changes)])


def test_active_original_owner_authority_is_independently_required():
    private, public = keys()
    with pytest.raises(PrimeFirstWriteHold, match="owner_scope_inactive"):
        review(verifier(public, authority=lambda *_: False),
               forecast(), envelopes=[attest(private)])


def test_empty_or_changed_canonical_readback_fail_closed():
    private, public = keys()
    with pytest.raises(PrimeFirstWriteHold, match="record_unavailable"):
        review(verifier(public, lookup=lambda *_: None),
               forecast(), envelopes=[attest(private)])
    def tampered(tenant, ref, when):
        return {
            "prediction_ref": ref, "tenant_scope_sha256": d(tenant),
            "prediction_sha256": prediction_digest(forecast(), tenant_id=tenant, as_of=when),
            "first_written_at": forecast()["journal_recorded_at"],
            "source_record_sha256": d("original-durable-first-write"),
            "append_only_uniqueness_verified": False,
        }
    with pytest.raises(PrimeFirstWriteHold, match="readback_conflict"):
        review(verifier(public, lookup=tampered),
               forecast(), envelopes=[attest(private)])


def test_original_reader_failure_does_not_expose_internal_data():
    private, public = keys()
    def broken(*_):
        raise RuntimeError("confidential@somebody.test")
    with pytest.raises(PrimeFirstWriteHold, match="reader_unavailable") as e:
        review(verifier(public, lookup=broken), forecast(),
               envelopes=[attest(private)])
    assert "confidential" not in str(e.value)


def test_caller_cannot_invent_original_public_key_in_envelope():
    private, public = keys()
    x = attest(private)
    x["public_key"] = public.hex()
    with pytest.raises(PrimeFirstWriteHold, match="unknown_or_malformed"):
        review(verifier(public), forecast(), envelopes=[x])


def test_replay_between_batches_is_not_solved_by_offline_signature_preflight():
    private, public = keys()
    v = verifier(public)
    signed = attest(private)
    first = review(v, forecast(), envelopes=[signed])
    second = review(v, forecast(), envelopes=[signed])
    assert first["atomic_durable_nonce_replay_protection_verified"] is False
    assert second["atomic_durable_nonce_replay_protection_verified"] is False
    assert "ATOMIC_DURABLE_REPLAY_RESERVATION_NOT_DEPLOYED" in second["blockers"]


def test_missing_or_extra_signed_predictions_rejected():
    private, public = keys()
    with pytest.raises(PrimeFirstWriteHold, match="cohort_required"):
        review(verifier(public), forecast(), envelopes=[])
    with pytest.raises(PrimeFirstWriteHold, match="cohort_required"):
        review(verifier(public), envelopes=[attest(private)])


def test_tenant_bound_digest_does_not_authenticate_real_tenant_membership():
    private, public = keys()
    x = review(verifier(public), forecast(), envelopes=[attest(private)])
    assert x["original_first_write_production_registry_authenticated"] is False
    assert x["source_issuer_live_key_provisioning_verified"] is False


def test_input_order_is_not_allowed_to_change_record_or_approval():
    private, public = keys()
    row = forecast()
    envelope = attest(private)
    before = deepcopy((row, envelope))
    review(verifier(public), row, envelopes=[envelope])
    assert (row, envelope) == before


def test_first_write_preflight_composes_with_original_predictive_bridge():
    from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review
    private, public = keys()
    r = build_predictive_revenue_brain_review(
        tenant_id=TENANT, as_of=NOW,
        original_forward_journal_predictions=[forecast()],
        signed_forward_first_write_attestations=[attest(private)],
        original_first_write_verifier=verifier(public),
    )
    assert r["prime_first_write_attestation_preflight_status"] == (
        "OFFLINE_SIGNED_FIRST_WRITE_READBACK_PREFLIGHT_PASS_RELEASE_HELD"
    )
    assert r["prime_first_write_production_authenticity_verified"] is False
    assert r["prime_durable_replay_reservation_verified"] is False
    assert r["prime_forward_prediction_journal_shadow"]["shadow_accuracy"] is None
    assert r["prime_forward_prediction_journal_shadow"]["journal_record_count_band"] == "0-4"
    assert r["database_writes"] is False
    assert r["revenue_verified"] is False
    assert r["forecast_model_promoted"] is False
    assert r["astra_dispatch_executed"] is False


def test_original_bridge_rejects_unsigned_first_write_claims_or_orphan_verifier():
    from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review
    private, public = keys()
    with pytest.raises(ValueError, match="verifier_and_predictions_required"):
        build_predictive_revenue_brain_review(
            tenant_id=TENANT, as_of=NOW,
            original_forward_journal_predictions=[forecast()],
            signed_forward_first_write_attestations=[attest(private)],
        )
    with pytest.raises(ValueError, match="attestations_required"):
        build_predictive_revenue_brain_review(
            tenant_id=TENANT, as_of=NOW,
            original_forward_journal_predictions=[forecast()],
            original_first_write_verifier=verifier(public),
        )
    with pytest.raises(ValueError, match="verifier_and_predictions_required"):
        build_predictive_revenue_brain_review(
            tenant_id=TENANT, as_of=NOW,
            signed_forward_first_write_attestations=[attest(private)],
            original_first_write_verifier=verifier(public),
        )


def test_bridge_first_write_proof_tampering_stops_before_calibration():
    from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review
    private, public = keys()
    signed = attest(private)
    signed["payload"]["prediction_sha256"] = d("after-the-fact-forecast")
    with pytest.raises(PrimeFirstWriteHold, match="digest_mismatch"):
        build_predictive_revenue_brain_review(
            tenant_id=TENANT, as_of=NOW,
            original_forward_journal_predictions=[forecast()],
            signed_forward_first_write_attestations=[signed],
            original_first_write_verifier=verifier(public),
        )
