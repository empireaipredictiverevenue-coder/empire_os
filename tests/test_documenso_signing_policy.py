from hashlib import sha256
import pytest

from empire_os.contract_signing import (
    prepare_agreement, observe_webhook, verify_artifacts,
)

SECRET = "x" * 48
ENV = "envelope_" + "a" * 16
AGREEMENT = "agreement-0001"


def agreement(**kwargs):
    r = {
        "agreement_id": AGREEMENT,
        "tenant_id": "tenant-001",
        "counterparty_entity_id": "contractor-0001",
        "contract_type": "contractor_growth", "provider": "documenso",
        "jurisdiction": "TX", "approved_pdf_sha256": "0" * 64,
        "agreement_version": 1, "legal_review_approved": True,
        "founder_approved": True, "terms_binding": True,
        "delivery_permission_checked": True,
        "signers": [
            {"role": "FOUNDER", "entity_id": "founder-001", "identity_verified": True},
            {"role": "COUNTERPARTY", "entity_id": "contractor-0001", "identity_verified": True}
        ],
    }
    r.update(kwargs)
    return r


def completed():
    return {
        "event": "DOCUMENT_COMPLETED",
        "createdAt": "2026-10-09T20:00:00.000Z",
        "payload": {
            "envelopeId": ENV, "externalId": AGREEMENT,
            "status": "COMPLETED",
            "completedAt": "2026-10-09T19:59:59Z",
            "recipients": [
                {"envelopeId": ENV, "role": "SIGNER",
                 "signingStatus": "SIGNED", "signedAt": "2026-10-09T19:55:00Z"},
                {"envelopeId": ENV, "role": "SIGNER",
                 "signingStatus": "SIGNED", "signedAt": "2026-10-09T19:59:59Z"},
            ],
        },
    }


def observe(data):
    return observe_webhook(data, supplied_secret=SECRET,
                           known_secret=SECRET,
                           expected_envelope_id=ENV,
                           expected_agreement_binding=AGREEMENT)


def test_approved_contract_is_only_review_ready_not_sent():
    r = prepare_agreement(agreement())
    assert r["state"] == "READY_FOR_FOUNDER_SIGNING_RELEASE_REVIEW"
    assert not r["envelope_distribute_authorized"]
    assert not r["signatures_executed"]


@pytest.mark.parametrize("other", [
    {"provider": "docusign"},
    {"founder_approved": False},
    {"legal_review_approved": False},
    {"approved_pdf_sha256": ""},
    {"terms_binding": False},
    {"delivery_permission_checked": False},
    {"signers": []},
    {"automated_signing_requested": True},
    {"agreement_version": True},
    {"contract_type": "other"},
])
def test_fail_closed_preflight(other):
    r = prepare_agreement(agreement(**other))
    assert r["state"] == "BLOCKED"
    assert r["blockers"]
    assert not r["envelope_create_authorized"]


def test_claims_contract_always_needs_special_legal_clearance():
    r = prepare_agreement(agreement(contract_type="licensed_claims_services"))
    assert "CLAIMS_LICENSING_AND_FEE_LEGAL_CLEARANCE_REQUIRED" in r["blockers"]


def test_hidden_claim_contingency_cannot_pass():
    r = prepare_agreement(agreement(claim_contingent_compensation=True))
    assert r["state"] == "BLOCKED"


def test_webhook_requires_shared_secret():
    with pytest.raises(ValueError, match="UNAUTHENTICATED"):
        observe_webhook(completed(), supplied_secret="wrong", known_secret=SECRET,
                        expected_envelope_id=ENV, expected_agreement_binding=AGREEMENT)


def test_document_signed_event_is_not_whole_agreement():
    d = completed()
    d["event"] = "DOCUMENT_SIGNED"
    d["payload"]["status"] = "PENDING"
    result = observe(d)
    assert result["state"] == "SIGNING_IN_PROGRESS"
    assert not result["commercial_terms_accepted"]


def test_completed_webhook_not_independent_signature_proof():
    result = observe(completed())
    assert result["state"] == "COMPLETED_EVENT_AWAITING_INDEPENDENT_ARTIFACT_PROOF"
    assert not result["signed_contract_verified"]
    assert not result["commercial_terms_accepted"]
    assert result == observe(completed())


def test_completed_event_requires_both_signers():
    d = completed()
    d["payload"]["recipients"].pop()
    with pytest.raises(ValueError, match="NOT_ALL_SIGNERS_SIGNED"):
        observe(d)


def test_completed_event_does_not_accept_missing_signature():
    d = completed()
    d["payload"]["recipients"][0]["signingStatus"] = "NOT_SIGNED"
    with pytest.raises(ValueError, match="NOT_ALL_SIGNERS_SIGNED"):
        observe(d)


def test_reject_wrong_envelope():
    d = completed()
    d["payload"]["envelopeId"] = "envelope_" + "b" * 16
    with pytest.raises(ValueError, match="ENVELOPE_MISMATCH"):
        observe(d)


def test_reject_wrong_external_agreement():
    d = completed()
    d["payload"]["externalId"] = "different-contract"
    with pytest.raises(ValueError, match="AGREEMENT_BINDING_MISMATCH"):
        observe(d)


def test_prior_terminal_state_cannot_be_overwritten():
    with pytest.raises(ValueError, match="CONFLICTING_TERMINAL_EVENT"):
        observe_webhook(completed(), supplied_secret=SECRET, known_secret=SECRET,
                        expected_envelope_id=ENV, expected_agreement_binding=AGREEMENT,
                        prior_terminal_event="DOCUMENT_CANCELLED")


def test_artifact_reconciliation_requires_api_and_audit():
    obs = observe(completed())
    with pytest.raises(ValueError, match="INDEPENDENT_ARTIFACT_VERIFICATION_MISSING"):
        verify_artifacts(obs, {"envelope_id": ENV, "agreement_binding": AGREEMENT,
                               "signed_pdf_sha256": "1" * 64})


def test_attested_artifact_still_is_not_payment():
    obs = observe(completed())
    result = verify_artifacts(obs, {
        "envelope_id": ENV, "agreement_binding": AGREEMENT,
        "authenticated_documenso_api_readback": True,
        "provider_status": "COMPLETED", "signed_pdf_integrity_verified": True,
        "audit_trail_integrity_verified": True, "signed_pdf_sha256": "1" * 64,
    })
    assert result["upstream_artifact_attested"]
    assert not result["canonical_registration_authorized"]
    assert not result["commercial_terms_accepted"]
    assert not result["revenue_recognized"]


def test_same_entity_cannot_be_both_signing_parties():
    r = agreement()
    r["signers"][1]["entity_id"] = "founder-001"
    assert "SIGNERS_MUST_BE_DIFFERENT_ENTITIES" in prepare_agreement(r)["blockers"]
