import os

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.deal_room import (
    AgreementDraft,
    AgreementRecipient,
    agreement_evidence_is_verified,
    build_documenso_envelope_plan,
    canonical_agreement_record,
    normalize_documenso_webhook,
)
from empire_os.deal_room_api import create_deal_room_router


def completed_payload():
    return {
        "event": "DOCUMENT_COMPLETED",
        "payload": {
            "envelopeId": "envelope_abc123",
            "externalId": "order-1",
            "status": "COMPLETED",
            "completedAt": "2026-09-21T10:30:00.000Z",
            "recipients": [
                {
                    "id": 1,
                    "role": "SIGNER",
                    "signingStatus": "SIGNED",
                    "signedAt": "2026-09-21T10:29:00.000Z",
                }
            ],
        },
        "createdAt": "2026-09-21T10:30:00.000Z",
    }


def test_agreement_plan_is_non_executing():
    draft = AgreementDraft(
        external_id="order-1",
        title="Pilot Agreement",
        document_sha256="a" * 64,
        recipients=(
            AgreementRecipient(
                email="buyer@example.com",
                name="Buyer",
            ),
        ),
        source_evidence_refs=("terms:1",),
        commercial_terms_ref="terms:1",
    )
    plan = build_documenso_envelope_plan(draft)
    assert plan["create_endpoint"] == "/envelope/create"
    assert plan["distribute_endpoint"] == "/envelope/distribute"
    assert plan["provider_execution"] is False
    assert plan["binding_acceptance"] is False
    assert plan["payment_request_created"] is False


def test_completed_webhook_requires_all_required_recipients():
    evidence = normalize_documenso_webhook(completed_payload())
    assert evidence.agreement_complete is True
    assert agreement_evidence_is_verified(evidence) is True
    assert evidence.canonical_commercial_mutation is False


def test_completed_status_without_signed_recipient_is_not_verified():
    payload = completed_payload()
    payload["payload"]["recipients"][0]["signingStatus"] = "NOT_SIGNED"
    evidence = normalize_documenso_webhook(payload)
    assert evidence.agreement_complete is False
    assert agreement_evidence_is_verified(evidence) is False


def test_webhook_api_fails_closed_without_secret(monkeypatch):
    monkeypatch.delenv("DOCUMENSO_WEBHOOK_SECRET", raising=False)
    app = FastAPI()
    app.include_router(create_deal_room_router())
    response = TestClient(app).post(
        "/v1/deal-room/webhooks/documenso/preview",
        json=completed_payload(),
    )
    assert response.status_code == 503


def test_webhook_api_verifies_secret_and_never_mutates(monkeypatch):
    monkeypatch.setenv("DOCUMENSO_WEBHOOK_SECRET", "secret-1")
    app = FastAPI()
    app.include_router(create_deal_room_router())
    response = TestClient(app).post(
        "/v1/deal-room/webhooks/documenso/preview",
        json=completed_payload(),
        headers={"X-Documenso-Secret": "secret-1"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["verified_webhook"] is True
    assert body["agreement_evidence_verified"] is True
    assert body["canonical_commercial_mutation"] is False
    assert body["revenue_recognition"] is False


def test_verified_documenso_evidence_maps_to_first_revenue_record():
    evidence = normalize_documenso_webhook(completed_payload())
    record = canonical_agreement_record(evidence)
    assert record["agreement_id"] == "envelope_abc123"
    assert record["status"] == "signed"
    assert record["evidence_verified"] is True
    assert record["canonical_commercial_mutation"] is False
