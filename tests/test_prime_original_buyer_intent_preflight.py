"""Tests the original signed Buyer Acquisition proof link, never a real buyer."""
from copy import deepcopy
from datetime import timedelta

import pytest

from empire_os.prime_original_buyer_intent_preflight import (
    PrimeOriginalBuyerIntentVerifier, PrimeBuyerIntentHold, PROOF_SCHEMA,
)
from test_prime_signed_owner_evidence_gateway import (
    NOW, TENANT, signer_pair, seal, receipt, verifier,
)


def proof(row=None, **changes):
    row = row or receipt()
    value = {
        "schema_version": PROOF_SCHEMA,
        "tenant_scope_sha256": row["tenant_scope_sha256"],
        "event_sha256": row["event_sha256"],
        "origin_sha256": row["origin_sha256"],
        "entity_sha256": row["entity_sha256"],
        "source_sha256": row["source_sha256"],
        "provider_received_at": row["received_at"],
        "reviewed_at": NOW.isoformat(),
        "original_provider_authenticated": True,
        "original_inbound_direction_verified": True,
        "original_provider_thread_parent_verified": True,
        "canonical_contact_and_tenant_binding_verified": True,
        "privacy_purpose_permitted": True,
        "suppression_and_deletion_policy_clear": True,
        "human_read_original_buyer_enquiry_reviewed": True,
        "read_only_owner_proof": True,
    }
    value.update(changes)
    return value


def health(status="BUYER_CONTRACT_CAPACITY_EVIDENCE_HOLD"):
    return {
        "schema_version": "empire.commercial.original_buyer_evidence_health.v1",
        "mode": "OBSERVE", "status": status, "execution_authority": "none",
        "database_writes": False, "outbound_authorized": False,
        "verified_purchase_events_claimed_by_this_report": None,
        "realized_revenue_cents_claimed_by_this_report": None,
    }


def gate(public, *, lookup=None, **kwargs):
    signed = verifier(public, **kwargs)
    original = PrimeOriginalBuyerIntentVerifier(
        signed_original_owner_gateway=signed,
        original_owner_lookup=(lookup or (lambda *_: proof())),
    )
    return signed, original


def run(original, env, status=None):
    return original.review(
        tenant_id=TENANT, as_of=NOW, signed_envelope=env,
        buyer_source_health=status,
    )


def test_original_signed_single_enquiry_can_reconcile_in_research_only():
    private, public = signer_pair()
    signed, original = gate(public)
    output = run(original, seal(private), health())
    assert original.uses_signed_owner_gateway(signed) is True
    assert output["status"] == "SIGNED_OWNER_AND_INBOUND_PROOF_CALLBACK_PREFLIGHT_ONLY_RELEASE_HELD"
    assert output["original_buyer_capacity_owner_review_status"] == "BUYER_CONTRACT_CAPACITY_EVIDENCE_HOLD"
    assert output["buyer_capacity_is_not_evidence_of_a_direct_inbound_enquiry"] is True
    assert output["genuine_original_inbound_event_live_verified_by_this_module"] is False
    assert output["buyer_intent_independently_verified"] is False
    assert output["source_admission_authorized"] is False
    assert output["durable_atomic_replay_prevention_verified"] is False
    assert output["verified_paid_order_count"] is None
    assert output["recognized_revenue_cents"] is None
    assert output["crm_writes"] is False
    assert output["empiredb_writes"] is False
    assert output["outbound_sent"] is False
    assert output["execution_authority"] == "none"
    assert TENANT not in str(output)
    assert "@" not in str(output)


@pytest.mark.parametrize("field", [
    "original_provider_authenticated",
    "original_inbound_direction_verified",
    "original_provider_thread_parent_verified",
    "canonical_contact_and_tenant_binding_verified",
    "privacy_purpose_permitted",
    "suppression_and_deletion_policy_clear",
    "human_read_original_buyer_enquiry_reviewed",
    "read_only_owner_proof",
])
def test_original_inbound_proof_incomplete_is_held(field):
    private, public = signer_pair()
    _, original = gate(public, lookup=lambda *_: proof(**{field: False}))
    status = run(original, seal(private))
    assert status["status"] == "ORIGINAL_INBOUND_BUYER_PROOF_INCOMPLETE_HOLD"
    assert status["owner_proof_missing_assertions"] == [field.upper() + "_NOT_PROVEN"]
    assert status["buyer_intent_independently_verified"] is False


@pytest.mark.parametrize("field", [
    "event_sha256", "origin_sha256", "tenant_scope_sha256",
    "entity_sha256", "source_sha256",
])
def test_original_owner_proof_must_link_exact_signed_receipt(field):
    private, public = signer_pair()
    _, original = gate(public, lookup=lambda *_: proof(**{field: "0" * 64}))
    with pytest.raises(PrimeBuyerIntentHold, match="source_identity_conflict"):
        run(original, seal(private))


def test_original_reader_failure_does_not_expose_provider_sensitive_details():
    private, public = signer_pair()
    def failure(*_):
        raise RuntimeError("sensitive-private-contact@example.com")
    _, original = gate(public, lookup=failure)
    with pytest.raises(PrimeBuyerIntentHold, match="reader_unavailable") as caught:
        run(original, seal(private))
    assert "sensitive-private" not in str(caught.value)


@pytest.mark.parametrize("row_changes", [
    {"evidence_class": "REALIZED_OUTCOME"},
    {"evidence_class": "GENERAL_INTEREST"},
    {"execution_authority": "send"},
])
def test_wrong_evidence_or_financial_promotion_never_enters_primes_buyer_gate(row_changes):
    private, public = signer_pair()
    raw = receipt()
    raw.update(row_changes)
    _, original = gate(public)
    with pytest.raises(PrimeBuyerIntentHold, match="original_signed_buyer_source_not_authenticated|not_an_original"):
        run(original, seal(private, row=raw))


def test_smart_crm_first_party_historical_receipt_requires_explicit_buyer_owner():
    private, public = signer_pair()
    source = receipt(owner="smart_crm")
    source["evidence_class"] = "EXPLICIT_ENQUIRY"
    signed = verifier(public, owner="smart_crm")
    original = PrimeOriginalBuyerIntentVerifier(
        signed_original_owner_gateway=signed,
        original_owner_lookup=lambda *_: proof(source),
    )
    with pytest.raises(PrimeBuyerIntentHold, match="not_an_original_single"):
        run(original, seal(private, row=source))


def test_tampered_signed_receipt_fails_even_if_proof_reader_returns_true():
    private, public = signer_pair()
    e = seal(private)
    e["payload"]["receipt"]["event_sha256"] = "f" * 64
    _, original = gate(public)
    with pytest.raises(PrimeBuyerIntentHold, match="signed_buyer_source_not_authenticated"):
        run(original, e)


def test_provider_proof_clock_must_precede_or_equal_receipt_clock():
    private, public = signer_pair()
    _, original = gate(public, lookup=lambda *_: proof(
        provider_received_at=(NOW + timedelta(minutes=1)).isoformat(),
    ))
    with pytest.raises(PrimeBuyerIntentHold, match="noncausal"):
        run(original, seal(private))


def test_probe_cannot_use_buyer_capacity_snapshot_as_source_proof():
    private, public = signer_pair()
    _, original = gate(public, lookup=lambda *_: health())
    with pytest.raises(PrimeBuyerIntentHold, match="exact_private_original"):
        run(original, seal(private), health())


def test_unsafe_buyer_capacity_source_pretend_paid_held():
    private, public = signer_pair()
    _, original = gate(public)
    with pytest.raises(PrimeBuyerIntentHold, match="unsafe_original"):
        run(original, seal(private), {
            **health(), "verified_purchase_events_claimed_by_this_report": 5,
        })


def test_only_exact_private_owner_proof_fields_accepted_no_pii():
    private, public = signer_pair()
    _, original = gate(public, lookup=lambda *_: proof(customer_email="private@example.com"))
    with pytest.raises(PrimeBuyerIntentHold, match="exact_private"):
        run(original, seal(private))


def test_original_source_inputs_stay_unchanged_and_no_buyer_identity_is_exported():
    private, public = signer_pair()
    envelope = seal(private)
    available = health()
    initial = deepcopy((envelope, available))
    _, original = gate(public)
    result = run(original, envelope, available)
    assert (envelope, available) == initial
    assert "event_sha256" not in result
    assert "entity_sha256" not in result
    assert "source_sha256" not in result
    assert result["production_release_authorized"] is False


def test_existing_prime_bridge_exposes_only_buyer_preflight_status_and_no_person():
    from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review
    private, public = signer_pair()
    signed, buyer = gate(public)
    bridge = build_predictive_revenue_brain_review(
        tenant_id=TENANT, as_of=NOW,
        signed_owner_evidence_envelopes=[seal(private)],
        original_owner_signature_verifier=signed,
        original_single_buyer_enquiry_verifier=buyer,
        original_buyer_source_health=health(),
    )
    assert bridge["prime_original_single_buyer_enquiry_preflight_status"] == (
        "SIGNED_OWNER_AND_INBOUND_PROOF_CALLBACK_PREFLIGHT_ONLY_RELEASE_HELD"
    )
    assert bridge["prime_first_buyer_intent_independently_verified"] is False
    assert bridge["prime_universal_evidence_shadow"]["source_connection_status"] == "OWNER_INPUT_UNAUTHENTICATED"
    assert bridge["prime_signed_owner_replay_protection_verified"] is False
    assert bridge["astra_dispatch_executed"] is False
    assert bridge["forecast_model_promoted"] is False
    assert bridge["outbound_sent"] is False
    assert TENANT not in str(bridge["prime_original_single_buyer_enquiry_preflight_status"])


def test_bridge_refuses_capacity_snapshot_alone_or_incompatible_owner_gateway():
    from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review
    private, public = signer_pair()
    signed, buyer = gate(public)
    with pytest.raises(ValueError, match="buyer_capacity_snapshot_cannot_authenticate"):
        build_predictive_revenue_brain_review(
            tenant_id=TENANT, as_of=NOW, original_buyer_source_health=health(),
        )
    second_gateway = verifier(public)
    with pytest.raises(ValueError, match="exact_original_signed_buyer_owner"):
        build_predictive_revenue_brain_review(
            tenant_id=TENANT, as_of=NOW,
            signed_owner_evidence_envelopes=[seal(private)],
            original_owner_signature_verifier=second_gateway,
            original_single_buyer_enquiry_verifier=buyer,
        )
    with pytest.raises(ValueError, match="exact_original_signed_buyer_owner"):
        build_predictive_revenue_brain_review(
            tenant_id=TENANT, as_of=NOW,
            original_single_buyer_enquiry_verifier=buyer,
        )
