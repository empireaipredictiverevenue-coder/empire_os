import json

import pytest

from empire_os.deal_room_documenso_provider import (
    ReadOnlyDocumenso, reconcile_envelope_readback, validate_origin,
    envelope_id_valid,
)

ID = "envelope_" + "a" * 16
EXPECTED = ("founder@empire-ai.co.uk", "partner@example.org")
EXT = "tenant-001:contract-001:v1"


class FakeResponse:
    def __init__(self, data, status_code=200, headers=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.content = json.dumps(data).encode("utf-8")
        self.closed = False

    def iter_content(self, chunk_size):
        for i in range(0, len(self.content), chunk_size):
            yield self.content[i:i+chunk_size]

    def close(self):
        self.closed = True


class FakeTransport:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def full_document(status="COMPLETED"):
    return {
        "id": ID, "type": "DOCUMENT", "status": status,
        "externalId": EXT, "completedAt": "2026-10-09T18:00:00Z",
        "recipients": [
            {"role": "SIGNER", "email": "founder@empire-ai.co.uk",
             "signingStatus": "SIGNED", "signedAt": "2026-10-09T17:55:00Z",
             "token": "internal-secret-do-not-echo"},
            {"role": "SIGNER", "email": "partner@example.org",
             "signingStatus": "SIGNED", "signedAt": "2026-10-09T18:00:00Z"},
        ],
        "documentMeta": {"message": "could be PII"},
    }


def test_readonly_documenso_account_uses_exact_origin_with_no_redirect():
    provider = ReadOnlyDocumenso("https://app.documenso.com/api/v2",
                                 "app.documenso.com", "api_" + "x" * 24)
    response = FakeResponse(full_document())
    transport = FakeTransport(response)
    result = provider.get_envelope(ID, session=transport)
    assert result["id"] == ID
    assert transport.calls[0][0] == "https://app.documenso.com/api/v2/envelope/" + ID
    assert transport.calls[0][1]["allow_redirects"] is False
    assert transport.calls[0][1]["stream"] is True
    assert transport.calls[0][1]["timeout"] <= 10
    assert response.closed


@pytest.mark.parametrize("origin,host", [
    ("http://app.documenso.com/api/v2", "app.documenso.com"),
    ("https://other.com/api/v2", "app.documenso.com"),
    ("https://user:pass@app.documenso.com/api/v2", "app.documenso.com"),
    ("https://app.documenso.com:444/api/v2", "app.documenso.com"),
    ("https://localhost/api/v2", "localhost"),
    ("https://127.0.0.1/api/v2", "127.0.0.1"),
    ("https://app.documenso.com/api/v2?secret=x", "app.documenso.com"),
])
def test_bad_origins_fail(origin, host):
    with pytest.raises(ValueError):
        validate_origin(origin, host)


def test_configured_existing_company_documenso_origin_allowed():
    assert validate_origin("https://sign.empire-ai.co.uk/api/v2",
                           "sign.empire-ai.co.uk") == "https://sign.empire-ai.co.uk/api/v2"


def test_missing_token_never_contacts_provider():
    transport = FakeTransport(FakeResponse(full_document()))
    with pytest.raises(ValueError, match="API_TOKEN_UNAVAILABLE"):
        ReadOnlyDocumenso("https://app.documenso.com/api/v2",
                          "app.documenso.com", "").get_envelope(ID, session=transport)
    assert not transport.calls


def test_provider_auth_failure_fails_closed():
    response = FakeResponse({"error": "token"}, status_code=401)
    transport = FakeTransport(response)
    with pytest.raises(ValueError, match="PROVIDER_READ_FAILED"):
        ReadOnlyDocumenso("https://app.documenso.com/api/v2",
                          "app.documenso.com", "api_"+"x"*24).get_envelope(ID, session=transport)
    assert response.closed


def test_signer_readback_is_not_contract_verified():
    result = reconcile_envelope_readback(full_document(), envelope_id=ID,
                                         agreement_external_id=EXT, signer_emails=EXPECTED)
    assert result["all_required_signers_completed"]
    assert not result["signed_pdf_verified"]
    assert not result["canonical_agreement_registered"]
    assert not result["revenue_recognized"]
    assert "partner@example.org" not in str(result)
    assert "internal-secret" not in str(result)


def test_pending_is_not_signed():
    result = reconcile_envelope_readback(full_document("PENDING"), envelope_id=ID,
                                         agreement_external_id=EXT, signer_emails=EXPECTED)
    assert not result["all_required_signers_completed"]


def test_identity_spoof_or_cross_tenant_refused():
    doc = full_document()
    doc["externalId"] = "tenant-other:contract-001:v1"
    with pytest.raises(ValueError, match="IDENTITY_MISMATCH"):
        reconcile_envelope_readback(doc, envelope_id=ID,
                                    agreement_external_id=EXT, signer_emails=EXPECTED)


def test_missing_signer_signature_fails_closed():
    doc = full_document()
    doc["recipients"][1]["signingStatus"] = "NOT_SIGNED"
    with pytest.raises(ValueError, match="COMPLETION_NOT_VERIFIED"):
        reconcile_envelope_readback(doc, envelope_id=ID,
                                    agreement_external_id=EXT, signer_emails=EXPECTED)


def test_duplicate_signer_cannot_disguise_missing_other_signature():
    doc = full_document()
    doc["recipients"][1]["email"] = "founder@empire-ai.co.uk"
    with pytest.raises(ValueError, match="SIGNERS_NOT_CONFIRMED"):
        reconcile_envelope_readback(doc, envelope_id=ID,
                                    agreement_external_id=EXT, signer_emails=EXPECTED)


def test_unsupported_envelope_id_rejected():
    assert not envelope_id_valid("../../../etc/passwd")
    assert not envelope_id_valid("envelope_/abc")
    assert envelope_id_valid(ID)


def test_readback_does_not_return_any_private_signing_url():
    doc = full_document()
    doc["signingUrl"] = "https://example.org/sign/private"
    summary = reconcile_envelope_readback(doc, envelope_id=ID,
                                          agreement_external_id=EXT, signer_emails=EXPECTED)
    assert "signingUrl" not in str(summary)


def test_existing_deal_room_readiness_is_safe_without_token(monkeypatch):
    from empire_os.deal_room import documenso_connection_readiness
    monkeypatch.delenv("DOCUMENSO_API_KEY", raising=False)
    monkeypatch.delenv("DOCUMENSO_API_BASE_URL", raising=False)
    monkeypatch.delenv("DOCUMENSO_TRUSTED_HOST", raising=False)
    status = documenso_connection_readiness()
    assert status["existing_instance_configured"] is False
    assert status["live_provider_verified"] is False
    assert not status["contract_distribution_enabled"]


def test_existing_deal_room_reads_preconfigured_documenso(monkeypatch):
    from empire_os.deal_room import read_documenso_agreement_status
    monkeypatch.setenv("DOCUMENSO_API_BASE_URL", "https://app.documenso.com/api/v2")
    monkeypatch.setenv("DOCUMENSO_TRUSTED_HOST", "app.documenso.com")
    monkeypatch.setenv("DOCUMENSO_API_KEY", "api_" + "x" * 24)
    result = read_documenso_agreement_status(
        tenant_id="tenant-001", agreement_id="contract-001", version=1,
        envelope_id=ID, signer_emails=EXPECTED,
        session=FakeTransport(FakeResponse(full_document())),
    )
    assert result["provider_status"] == "COMPLETED"
    assert result["signed_pdf_verified"] is False
    assert result["canonical_agreement_registered"] is False


def test_existing_deal_room_blocks_missing_tenant_binding(monkeypatch):
    from empire_os.deal_room import read_documenso_agreement_status
    with pytest.raises(ValueError, match="CANONICAL_TENANT"):
        read_documenso_agreement_status(
            tenant_id="", agreement_id="contract-001", version=1,
            envelope_id=ID, signer_emails=EXPECTED, session=FakeTransport(FakeResponse(full_document())),
        )



def test_existing_deal_room_uses_selected_documenso_instance(monkeypatch):
    from empire_os.deal_room import AgreementDraft, AgreementRecipient, build_documenso_envelope_plan
    monkeypatch.setenv("DOCUMENSO_API_BASE_URL", "https://sign.empire-ai.co.uk/api/v2")
    monkeypatch.setenv("DOCUMENSO_TRUSTED_HOST", "sign.empire-ai.co.uk")
    draft = AgreementDraft(
        external_id="tenant-001:agreement-001:v1",
        title="Contractor pilot",
        document_sha256="a" * 64,
        recipients=(AgreementRecipient(email="partner@example.org", name="Partner"),),
        source_evidence_refs=("terms:contract-001",),
        commercial_terms_ref="terms:contract-001",
    )
    plan = build_documenso_envelope_plan(draft)
    assert plan["api_base_url"] == "https://sign.empire-ai.co.uk/api/v2"
    assert plan["provider_execution"] is False
