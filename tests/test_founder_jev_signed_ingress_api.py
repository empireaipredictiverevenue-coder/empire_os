"""Opt-in founder signed ingress route never grants buyer-contact authority."""
import base64
from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from empire_os.founder_jev_api import create_founder_jev_router
from empire_os.founder_dashboard_service import build_founder_dashboard_service
from empire_os.owned_imap_mailbox import OwnedIMAPMailboxProvider
from empire_os.revenue_crm_api import AuthenticatedRevenueCrmRead
from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository
from empire_os.jev_gtm_signed_transport_review import (
    DOMAIN, SCHEMA, ISSUER, AUDIENCE,
)

TENANT = str(UUID(int=1))
PROSPECT = str(UUID(int=2))
INTENT = str(UUID(int=3))
EVENT = str(UUID(int=4))
KEY = b"NOT_AN_ACTUAL_PRODUCTION_KEY_00000000000000"
PRIVATE = Ed25519PrivateKey.generate()
PUBLIC = {"pinned-ingress-v1": PRIVATE.public_key()}
PATH = f"/v1/founder-jev/crm-prospects/{PROSPECT}/signed-transport/review"


class Mailbox(OwnedIMAPMailboxProvider):
    def __init__(self):
        super().__init__(
            host="mail.empire-ai.co.uk",
            username="phil@mail.empire-ai.co.uk",
            password="fake-test-only",
        )
        self.calls = []

    def list_received(self, *, limit):
        self.calls.append("inbox")
        return [{
            "id": "imap:inbox:77:2", "provider": "owned_imap",
            "message_id": "<received@buyer.example>",
            "in_reply_to": "<sent@empire.example>",
            "to": [f"reply+{INTENT}@mail.empire-ai.co.uk"],
            "source_received_at_verified": False,
            "canonical_thread_identity_verified": False,
            "canonical_contact_identity_verified": False,
            "text": "SECRET BUYER DATA",
        }]

    def list_sent(self, *, limit):
        self.calls.append("sent")
        return [{
            "id": "imap:sent:77:1", "provider": "owned_imap",
            "message_id": "<sent@empire.example>",
            "canonical_thread_identity_verified": False,
            "canonical_contact_identity_verified": False,
        }]


class FakeScopedReader(PostgresRevenueCrmRepository):
    def __init__(self):
        super().__init__("synthetic", tenant_id=TENANT)

    def prospect(self, prospect_id):
        assert prospect_id == PROSPECT
        return {"tenant_id": TENANT, "prospect_id": PROSPECT}


def scope(_request):
    return AuthenticatedRevenueCrmRead(TENANT, FakeScopedReader())


def receipt():
    now = int(datetime.now(timezone.utc).timestamp())
    claims = {
        "issuer": ISSUER, "audience": AUDIENCE,
        "event_id": EVENT,
        "tenant_id": TENANT, "intent_id": INTENT,
        "message_id": "<received@buyer.example>",
        "in_reply_to": "<sent@empire.example>",
        "received_at": now - 30, "issued_at": now - 29,
        "boundary": "first_party_smtp_ingress", "direction": "inbound",
        "smtp_result": "dmarc_aligned_pass",
        "raw_message_sha256": sha256(b"synthetic bytes").hexdigest(),
    }
    encoded = DOMAIN + json.dumps(
        claims, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    signature = base64.urlsafe_b64encode(
        PRIVATE.sign(encoded)
    ).rstrip(b"=").decode("ascii")
    return {
        "schema_version": SCHEMA, "key_id": "pinned-ingress-v1",
        "claims": claims, "signature": signature,
    }


def client(*, founder, resolver=scope, source=None, provider=None, keys=None):
    app = FastAPI()
    app.include_router(create_founder_jev_router(
        authorizer=founder,
        resolve_authenticated_crm=resolver,
        mailbox_provider=provider or Mailbox(),
        mailbox_hmac_key=KEY,
        signed_receipt_source=source or (lambda request, prospect: [receipt()]),
        pinned_ingress_public_keys=PUBLIC if keys is None else keys,
    ))
    return TestClient(app)


def test_default_founder_service_does_not_mount_signed_transport():
    app = build_founder_dashboard_service()
    assert "/v1/founder-jev/crm-prospects/{prospect_id}/signed-transport/review" not in app.openapi()["paths"]


def test_public_pinned_key_is_required_before_route_registration():
    with pytest.raises(ValueError, match="signed ingress requires"):
        create_founder_jev_router(
            authorizer=lambda req: True,
            resolve_authenticated_crm=scope,
            mailbox_provider=Mailbox(), mailbox_hmac_key=KEY,
            signed_receipt_source=lambda request, prospect: [receipt()],
            pinned_ingress_public_keys={},
        )


def test_denied_founder_cannot_read_db_receipts_or_mailbox():
    mailbox = Mailbox()
    calls = []
    response = client(
        founder=lambda req: False, provider=mailbox,
        resolver=lambda req: calls.append("crm"),
        source=lambda req, prospect: calls.append("receipt"),
    ).get(PATH)
    assert response.status_code == 403
    assert mailbox.calls == []
    assert calls == []


def test_unbound_crm_tenant_does_not_collect_receipts():
    mailbox = Mailbox()
    touched = []
    response = client(
        founder=lambda req: True,
        provider=mailbox,
        resolver=lambda request: None,
        source=lambda req, prospect: touched.append("receipt"),
    ).get(PATH)
    assert response.status_code == 401
    assert mailbox.calls == []
    assert touched == []


def test_mismatched_crm_tenant_fails_before_mailbox_or_receipts():
    mailbox = Mailbox()
    touched = []
    response = client(
        founder=lambda req: True, provider=mailbox,
        resolver=lambda req: AuthenticatedRevenueCrmRead(
            tenant_id=str(UUID(int=999)), repository=FakeScopedReader()
        ),
        source=lambda req, prospect: touched.append("receipt"),
    ).get(PATH)
    assert response.status_code == 503
    assert touched == []
    assert mailbox.calls == []


def test_approved_prospect_returns_only_signed_assertion_status():
    mailbox = Mailbox()
    response = client(
        founder=lambda req: True, provider=mailbox,
    ).get(PATH)
    assert response.status_code == 200
    packet = response.json()
    assert mailbox.calls == ["inbox", "sent"]
    assert packet["signed_assertions_matched_to_imap_headers"] == 1
    assert packet["original_smtp_provider_authentication_independently_proven"] is False
    assert packet["buyer_reply_count_verified"] is None
    assert packet["recognized_revenue"] is None
    assert packet["outbound_authorized"] is False
    for sensitive in (
        "SECRET BUYER DATA", "<received@buyer.example>",
        "<sent@empire.example>", TENANT, INTENT,
    ):
        assert sensitive not in response.text


def test_tampered_signature_returns_sanitized_503_without_false_match():
    signed = receipt()
    signed["claims"]["smtp_result"] = "dmarc_fail"
    response = client(
        founder=lambda req: True,
        source=lambda req, prospect: [signed],
    ).get(PATH)
    assert response.status_code == 503
    assert "dmarc_fail" not in response.text


def test_bad_prospect_id_rejected_before_receipt_load():
    calls = []
    response = client(
        founder=lambda req: True,
        source=lambda req, prospect: calls.append("receipt"),
    ).get("/v1/founder-jev/crm-prospects/invalid/signed-transport/review")
    assert response.status_code == 400
    assert calls == []


def test_oversized_limit_rejected_before_database_or_mailbox():
    mailbox = Mailbox()
    calls = []
    response = client(
        founder=lambda req: True, provider=mailbox,
        resolver=lambda req: calls.append("db"),
    ).get(PATH + "?limit=100")
    assert response.status_code == 422
    assert mailbox.calls == []
    assert calls == []


def test_signed_receipt_source_failure_sanitized():
    def unavailable(req, prospect):
        raise RuntimeError("SECRET production transport credential")
    response = client(
        founder=lambda req: True,
        source=unavailable,
    ).get(PATH)
    assert response.status_code == 503
    assert "SECRET" not in response.text


def test_status_does_not_claim_deployed_producer_or_verified_buyers():
    packet = client(founder=lambda req: True).get("/v1/founder-jev/status").json()
    assert packet["signed_first_party_ingress_verifier_implemented"] is True
    assert packet["signed_first_party_ingress_producer_configured"] is True
    assert packet["signed_first_party_ingress_producer_independently_audited"] is False
    assert packet["independently_verified_buyer_replies"] is None
    assert packet["production_activated"] is False
