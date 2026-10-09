from copy import deepcopy
from hashlib import sha256

import pytest

from empire_os.contract_signing.offline_envelope import (
    preview_create, parse_authenticated_envelope,
)

PDF = b"%PDF-1.7\n" + b"dummy-boundary-preflight-only" * 8 + b"\n%%EOF\n"
ENV = "envelope_" + "a" * 16


def approved_agreement():
    return {
        "agreement_id": "agreement-001", "tenant_id": "tenant-001",
        "counterparty_entity_id": "contractor-001",
        "contract_type": "contractor_growth", "provider": "documenso",
        "jurisdiction": "TX", "agreement_version": 1,
        "approved_pdf_sha256": sha256(PDF).hexdigest(),
        "document_title": "Contractor Growth Pilot",
        "legal_review_approved": True, "founder_approved": True,
        "terms_binding": True, "delivery_permission_checked": True,
        "signers": [
            {"role": "FOUNDER", "entity_id": "founder-001", "identity_verified": True},
            {"role": "COUNTERPARTY", "entity_id": "contractor-001", "identity_verified": True},
        ],
    }


def signers():
    return [
        {"role": "FOUNDER", "entity_id": "founder-001",
         "name": "Founder", "email": "founder@empire-ai.co.uk",
         "fields": [{"type": "SIGNATURE", "page": 1, "positionX": 10,
                     "positionY": 80, "width": 30, "height": 5}]},
        {"role": "COUNTERPARTY", "entity_id": "contractor-001",
         "name": "Partner", "email": "partner@example.org",
         "fields": [{"type": "SIGNATURE", "page": 1, "positionX": 60,
                     "positionY": 80, "width": 30, "height": 5}]},
    ]


def provider_response():
    return {
        "id": ENV, "externalId": "tenant-001:agreement-001:v1",
        "type": "DOCUMENT", "status": "COMPLETED",
        "completedAt": "2026-10-09T19:40:00Z",
        "recipients": [
            {"role": "SIGNER", "email": "founder@empire-ai.co.uk",
             "signingStatus": "SIGNED", "signedAt": "2026-10-09T19:39:00Z",
             "token": "SECRET_SIGNER_TOKEN"},
            {"role": "SIGNER", "email": "partner@example.org",
             "signingStatus": "SIGNED", "signedAt": "2026-10-09T19:40:00Z"},
        ],
        "signingUrl": "https://sign.empire-ai.co.uk/sign/private",
    }


def parsed(response):
    return parse_authenticated_envelope(
        response, expected_id=ENV,
        expected_external_id="tenant-001:agreement-001:v1",
        expected_signer_emails=("founder@empire-ai.co.uk", "partner@example.org"),
    )


def test_correct_documenso_v2_shape_but_no_action():
    preview = preview_create(approved_agreement(), PDF, signers())
    assert preview["endpoint"] == "/api/v2/envelope/create"
    assert preview["content_type"] == "multipart/form-data"
    assert preview["json_field"] == "payload"
    assert preview["file_field"] == "files"
    assert preview["payload"]["type"] == "DOCUMENT"
    assert preview["payload"]["externalId"] == "tenant-001:agreement-001:v1"
    assert len(preview["payload"]["recipients"]) == 2
    assert all(len(x["fields"]) == 1 and x["fields"][0]["type"] == "SIGNATURE"
               for x in preview["payload"]["recipients"])
    assert preview["create_authorized"] is False
    assert preview["distribute_authorized"] is False
    assert not preview["pdf_parser_verified"]


def test_pdf_tampering_blocked():
    with pytest.raises(ValueError, match="APPROVED_PDF_HASH_MISMATCH"):
        preview_create(approved_agreement(), PDF.replace(b"dummy", b"alter"), signers())


@pytest.mark.parametrize("blob", [b"", b"contract text", b"%PDF\n" + b"x"*300, PDF[:120]])
def test_malformed_pdf_blocked(blob):
    with pytest.raises(ValueError):
        preview_create(approved_agreement(), blob, signers())


@pytest.mark.parametrize("field", [
    {"type": "SIGNATURE", "page": 0, "positionX": 1, "positionY": 70, "width": 20, "height": 8},
    {"type": "SIGNATURE", "page": 1, "positionX": 90, "positionY": 70, "width": 20, "height": 8},
    {"type": "DATE", "page": 1, "positionX": 1, "positionY": 70, "width": 20, "height": 8},
    {"type": "SIGNATURE", "page": True, "positionX": 1, "positionY": 70, "width": 20, "height": 8},
])
def test_invalid_or_missing_signature_fields_blocked(field):
    rows = signers()
    rows[0]["fields"] = [field]
    with pytest.raises(ValueError):
        preview_create(approved_agreement(), PDF, rows)


def test_wrong_signing_entity_rejected():
    rows = signers()
    rows[1]["entity_id"] = "other-contractor"
    with pytest.raises(ValueError, match="SIGNER_IDENTITY_BINDING_MISMATCH"):
        preview_create(approved_agreement(), PDF, rows)


def test_duplicate_signing_email_rejected():
    rows = signers()
    rows[1]["email"] = rows[0]["email"]
    with pytest.raises(ValueError, match="BOTH_DISTINCT_SIGNERS_REQUIRED"):
        preview_create(approved_agreement(), PDF, rows)


def test_contract_draft_requires_founder_release():
    record = approved_agreement()
    record["founder_approved"] = False
    with pytest.raises(ValueError, match="AGREEMENT_PREFLIGHT_BLOCKED"):
        preview_create(record, PDF, signers())


def test_readback_completed_is_not_contract_acceptance_or_payment():
    clean = parsed(provider_response())
    assert clean["provider_status"] == "COMPLETED"
    assert clean["all_signers_marked_signed"]
    assert not clean["contract_accepted"]
    assert not clean["canonical_registration_authorized"]
    assert not clean["revenue_recognized"]
    assert "SECRET_SIGNER_TOKEN" not in str(clean)
    assert "partner@example.org" not in str(clean)


def test_pending_provider_does_not_mark_signed():
    data = provider_response()
    data["status"] = "PENDING"
    data["completedAt"] = None
    assert parsed(data)["all_signers_marked_signed"] is False


def test_provider_wrong_binding_rejected():
    data = provider_response()
    data["externalId"] = "tenant-002:agreement-001:v1"
    with pytest.raises(ValueError, match="PROVIDER_DOCUMENT_BINDING_MISMATCH"):
        parsed(data)


def test_missing_signer_proof_rejected():
    data = provider_response()
    data["recipients"][1]["signingStatus"] = "NOT_SIGNED"
    with pytest.raises(ValueError, match="SIGNING_COMPLETION_NOT_PROVED"):
        parsed(data)


def test_duplicate_forged_signer_cannot_replace_real_counterparty():
    data = provider_response()
    data["recipients"][1]["email"] = "founder@empire-ai.co.uk"
    with pytest.raises(ValueError, match="PROVIDER_SIGNERS_NOT_BOUND"):
        parsed(data)


def test_replay_same_provider_snapshot_is_stable():
    assert parsed(provider_response()) == parsed(provider_response())
