"""Founder JEV conditional read-only owned mailbox evidence routes."""
from uuid import UUID
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

import empire_os.founder_jev_api as api
from empire_os.founder_jev_api import create_founder_jev_router
from empire_os.founder_dashboard_service import build_founder_dashboard_service
from empire_os.owned_imap_mailbox import OwnedIMAPMailboxProvider
from empire_os.revenue_crm_api import AuthenticatedRevenueCrmRead
from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository

TENANT = str(UUID(int=1))
PROSPECT = str(UUID(int=2))
INTENT = str(UUID(int=3))
REPLY = str(UUID(int=4))
KEY = b"fake-test-independent-HMAC-key-not-a-prod-secret"
PATH = "/v1/founder-jev/mailbox/headers/review"
ALIGN = "/v1/founder-jev/crm-prospects/" + PROSPECT + "/mailbox-alignment"


class MockIMAP(OwnedIMAPMailboxProvider):
    def __init__(self):
        super().__init__(
            host="mail.empire-ai.co.uk", username="phil@mail.empire-ai.co.uk",
            password="fake-test-not-real",
        )
        self.calls = []

    def list_received(self, *, limit):
        self.calls.append(("received", limit))
        return [{
            "provider": "owned_imap",
            "id": "imap:inbox:77:4",
            "message_id": "<recv@buyer.example>",
            "in_reply_to": "<sent@empire.example>",
            "to": [f"reply+{INTENT}@mail.empire-ai.co.uk"],
            "source_received_at_verified": False,
            "canonical_contact_identity_verified": False,
            "canonical_thread_identity_verified": False,
            "text": "SECRET BUYER TEXT: PRICING",
        }]

    def list_sent(self, *, limit):
        self.calls.append(("sent", limit))
        return [{
            "provider": "owned_imap",
            "id": "imap:sent:77:3",
            "message_id": "<sent@empire.example>",
            "canonical_contact_identity_verified": False,
            "canonical_thread_identity_verified": False,
            "text": "private sales offer",
        }]


def mock_reader():
    return PostgresRevenueCrmRepository(
        "fake-test-connection",
        tenant_id=TENANT,
        connect_factory=lambda _: (_ for _ in ()).throw(
            AssertionError("no external database in isolated API test")
        ),
    )


def canonical_scope(_):
    return AuthenticatedRevenueCrmRead(tenant_id=TENANT, repository=mock_reader())


def client(*, authorizer=None, resolver=None, provider=None, key=None):
    app = FastAPI()
    app.include_router(create_founder_jev_router(
        authorizer=authorizer,
        resolve_authenticated_crm=resolver,
        mailbox_provider=provider,
        mailbox_hmac_key=key,
    ))
    return TestClient(app)


def test_default_service_has_no_live_mailbox_or_alignment_route():
    app = build_founder_dashboard_service()
    routes = app.openapi()["paths"]
    assert PATH not in routes
    assert "/v1/founder-jev/crm-prospects/{prospect_id}/mailbox-alignment" not in routes
    status = TestClient(app).get("/v1/founder-jev/status").json()
    assert status["owned_imap_header_review_configured"] is False
    assert status["mailbox_crm_alignment_verified"] is False


def test_missing_independent_founder_authority_fails_before_router_installed():
    with pytest.raises(ValueError, match="must be paired"):
        create_founder_jev_router(mailbox_provider=MockIMAP(), mailbox_hmac_key=KEY)
    with pytest.raises(ValueError, match="HMAC"):
        create_founder_jev_router(
            authorizer=lambda req: True,
            mailbox_provider=MockIMAP(), mailbox_hmac_key=b"weak",
        )


def test_authorizer_denial_does_not_read_private_imap():
    provider = MockIMAP()
    response = client(
        authorizer=lambda req: False, provider=provider, key=KEY,
    ).get(PATH)
    assert response.status_code == 403
    assert provider.calls == []


def test_authorizer_exception_fails_closed():
    provider = MockIMAP()
    def fail(req): raise RuntimeError("secret approval check error")
    response = client(authorizer=fail, provider=provider, key=KEY).get(PATH)
    assert response.status_code == 403
    assert provider.calls == []


def test_only_approved_founder_can_view_hmac_headers_not_private_data():
    provider = MockIMAP()
    response = client(
        authorizer=lambda req: True, provider=provider, key=KEY,
    ).get(PATH + "?limit=2")
    assert response.status_code == 200
    assert provider.calls == [("received", 2), ("sent", 2)]
    packet = response.json()
    assert packet["provider_receipts_authenticated"] is False
    assert packet["commercial_buyer_reply_count"] is None
    assert packet["rows"][0]["sent_rfc_parent_unique"] is True
    assert packet["execution_authority"] == "none"
    for private in ("SECRET BUYER TEXT", "<recv@buyer.example>", "private sales offer",
                    "phil@mail.empire-ai.co.uk", INTENT):
        assert private not in response.text


def test_no_crm_resolver_means_no_alignment_route():
    api_client = client(authorizer=lambda req: True, provider=MockIMAP(), key=KEY)
    assert api_client.get(ALIGN).status_code == 404


def test_authorizer_denial_prevents_both_db_and_imap():
    provider = MockIMAP()
    resolver_calls = []
    response = client(
        authorizer=lambda req: False,
        resolver=lambda req: resolver_calls.append(True),
        provider=provider, key=KEY,
    ).get(ALIGN)
    assert response.status_code == 403
    assert resolver_calls == []
    assert provider.calls == []


def test_missing_canonical_crm_scope_denies_mailbox_alignment():
    provider = MockIMAP()
    response = client(
        authorizer=lambda req: True,
        resolver=lambda req: None,
        provider=provider, key=KEY,
    ).get(ALIGN)
    assert response.status_code == 401
    assert provider.calls == []


def test_crm_session_tenant_mismatch_prevents_mailbox_call():
    provider = MockIMAP()
    response = client(
        authorizer=lambda req: True,
        resolver=lambda req: AuthenticatedRevenueCrmRead(
            tenant_id=str(UUID(int=99)), repository=mock_reader(),
        ),
        provider=provider, key=KEY,
    ).get(ALIGN)
    assert response.status_code == 503
    assert provider.calls == []


def test_crm_original_reply_051_missing_fails_closed_and_no_mailbox_read():
    provider = MockIMAP()
    response = client(
        authorizer=lambda req: True,
        resolver=canonical_scope, provider=provider, key=KEY,
    ).get(ALIGN)
    assert response.status_code == 503
    assert provider.calls == []
    assert "fake-test-connection" not in response.text


def test_mocked_valid_crm_candidate_and_owned_imap_have_only_alias_hints(monkeypatch):
    provider = MockIMAP()
    def simulated_source(*args, **kwargs):
        return {
            "schema_version": "empire.jev.reply_candidate_review.v1",
            "mode": "OBSERVE", "prospect_id": PROSPECT,
            "candidate_count": 1,
            "candidate_counts_by_unverified_class": {"positive": 1},
            "review_fingerprint": "f"*64,
            "items": [{
                "reply_ref": REPLY, "intent_ref": INTENT,
                "classification_unverified": "positive",
                "received_at": "2026-10-14T09:00:00+00:00",
                "conversation_match_count": 1,
                "provider_reference_present": True,
                "provenance_status": "REVIEW_ONLY_UNAUTHENTICATED",
                "blocker": "ORIGINAL_PROVIDER_AND_CONTACT_PROOF_PENDING",
                "positive_buyer_reply_verified": False,
                "outbound_authorized": False,
            }],
            "full_tenant_inbox_verified": False,
            "original_provider_authenticated_count": None,
            "genuine_buying_conversations_verified": None,
            "contact_binding_verified_count": None,
            "provider_receipts_independently_verified": False,
            "new_database_authority": False, "send_authorized": False,
            "recognized_revenue": None, "execution_authority": "none",
        }
    monkeypatch.setattr(api, "review_jev_reply_candidates", simulated_source)
    response = client(
        authorizer=lambda req: True, resolver=canonical_scope,
        provider=provider, key=KEY,
    ).get(ALIGN)
    assert response.status_code == 200
    data = response.json()
    assert data["rows"][0]["linkage_status"] == "ALIAS_UNIQUE_UNAUTHENTICATED"
    assert data["buyer_conversation_count_verified"] is None
    assert data["original_provider_authenticated"] is False
    assert data["outbound_authorized"] is False
    assert "SECRET" not in response.text
    assert INTENT not in response.text


def test_overbound_request_rejected_before_mailbox():
    provider = MockIMAP()
    response = client(
        authorizer=lambda req: True, provider=provider, key=KEY,
    ).get(PATH + "?limit=101")
    assert response.status_code == 422
    assert provider.calls == []


def test_contract_rejects_injected_contact_field(monkeypatch):
    provider = MockIMAP()
    original = api.review_owned_mailbox_headers
    def leak(*args, **kwargs):
        result = original(*args, **kwargs)
        result["rows"][0]["sender_email"] = "private@example.invalid"
        return result
    monkeypatch.setattr(api, "review_owned_mailbox_headers", leak)
    response = client(
        authorizer=lambda req: True, provider=provider, key=KEY,
    ).get(PATH)
    assert response.status_code == 503
    assert "private@example.invalid" not in response.text
