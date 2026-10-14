"""Request-scoped reply candidate API: metadata only, never authenticated buyers."""
from datetime import datetime, timezone
from uuid import UUID
from fastapi import FastAPI
from fastapi.testclient import TestClient

import pytest

import empire_os.founder_jev_api as api
from empire_os.founder_jev_api import create_founder_jev_router
from empire_os.founder_dashboard_service import build_founder_dashboard_service
from empire_os.revenue_crm_api import AuthenticatedRevenueCrmRead
from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository

TENANT, PROSPECT, REPLY, INTENT, OTHER = [str(UUID(int=n)) for n in range(1, 6)]
PATH = "/v1/founder-jev/crm-prospects/" + PROSPECT + "/reply-candidates"


def repo():
    return PostgresRevenueCrmRepository(
        "test-dsn", tenant_id=TENANT,
        connect_factory=lambda dsn: (_ for _ in ()).throw(
            AssertionError("database not needed for API auth test")
        ),
    )


def fake_packet():
    return {
        "schema_version": "empire.jev.reply_candidate_review.v1",
        "mode": "OBSERVE",
        "prospect_id": PROSPECT,
        "candidate_count": 1,
        "candidate_counts_by_unverified_class": {"positive": 1},
        "review_fingerprint": "f" * 64,
        "items": [{
            "reply_ref": REPLY,
            "intent_ref": INTENT,
            "classification_unverified": "positive",
            "received_at": datetime(2026, 10, 14, 9, tzinfo=timezone.utc).isoformat(),
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
        "new_database_authority": False,
        "send_authorized": False,
        "recognized_revenue": None,
        "execution_authority": "none",
    }


def app_client(authorizer, resolver):
    app = FastAPI()
    app.include_router(create_founder_jev_router(
        authorizer=authorizer, resolve_authenticated_crm=resolver,
    ))
    return TestClient(app)


def good_scope(_request):
    return AuthenticatedRevenueCrmRead(tenant_id=TENANT, repository=repo())


def test_default_service_has_no_reply_candidate_reader_route():
    paths = build_founder_dashboard_service().openapi()["paths"]
    assert "/v1/founder-jev/crm-prospects/{prospect_id}/reply-candidates" not in paths


def test_denied_founder_never_calls_scope_resolver():
    accesses = []
    response = app_client(
        lambda request: False,
        lambda request: accesses.append("called"),
    ).get(PATH)
    assert response.status_code == 403
    assert accesses == []


def test_unbound_tenant_cannot_read_reply_sources():
    assert app_client(lambda req: True, lambda req: None).get(PATH).status_code == 401


def test_mismatched_canonical_crm_tenant_is_denied(monkeypatch):
    called = []
    monkeypatch.setattr(api, "review_jev_reply_candidates", lambda *_args, **_kwargs: called.append(True))
    response = app_client(
        lambda request: True,
        lambda request: AuthenticatedRevenueCrmRead(tenant_id=OTHER, repository=repo()),
    ).get(PATH)
    assert response.status_code == 503
    assert called == []


def test_verified_scope_routes_to_bounded_source_and_no_contact_authority(monkeypatch):
    requests = []
    def source(repository, *, prospect_id, limit, as_of):
        requests.append((repository.tenant_id, prospect_id, limit))
        return fake_packet()
    monkeypatch.setattr(api, "review_jev_reply_candidates", source)
    response = app_client(lambda req: True, good_scope).get(PATH + "?limit=7")
    assert response.status_code == 200
    assert requests == [(TENANT, PROSPECT, 7)]
    assert response.json()["genuine_buying_conversations_verified"] is None
    assert response.json()["items"][0]["positive_buyer_reply_verified"] is False
    assert response.json()["send_authorized"] is False


def test_extra_pii_field_rejected_from_source(monkeypatch):
    value = fake_packet()
    value["items"][0]["sender_email"] = "private@example.invalid"
    monkeypatch.setattr(api, "review_jev_reply_candidates", lambda *args, **kw: value)
    response = app_client(lambda req: True, good_scope).get(PATH)
    assert response.status_code == 503
    assert "private@example.invalid" not in response.text


def test_forged_provider_authentication_disposition_rejected(monkeypatch):
    value = fake_packet()
    value["items"][0]["positive_buyer_reply_verified"] = True
    monkeypatch.setattr(api, "review_jev_reply_candidates", lambda *args, **kw: value)
    response = app_client(lambda req: True, good_scope).get(PATH)
    assert response.status_code == 503


def test_oversized_limit_rejected_before_resolver():
    touched = []
    response = app_client(
        lambda req: True,
        lambda req: touched.append("called"),
    ).get(PATH + "?limit=501")
    assert response.status_code == 422
    assert touched == []


def test_source_051_missing_returns_safe_503(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("database password secret")
    monkeypatch.setattr(api, "review_jev_reply_candidates", fail)
    response = app_client(lambda req: True, good_scope).get(PATH)
    assert response.status_code == 503
    assert "password" not in response.text


def test_status_claims_prepared_not_applied():
    status = app_client(lambda req: True, good_scope).get("/v1/founder-jev/status").json()
    assert status["reply_candidate_reader_prepared"] is True
    assert status["reply_candidate_migration_051_applied"] is None
    assert status["verified_original_reply_count"] is None
    assert status["production_activated"] is False
