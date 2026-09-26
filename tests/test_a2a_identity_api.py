from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.a2a_identity import InMemoryNonceRegistry
from empire_os.a2a_identity_api import create_a2a_identity_router


NOW = datetime(2026, 9, 19, 20, 30, tzinfo=timezone.utc)


def client(verifier=None, trusted=None, registry=None):
    app = FastAPI()
    app.include_router(
        create_a2a_identity_router(
            verifier=verifier,
            trusted_key_ids=trusted,
            nonce_registry=registry,
            clock=lambda: NOW,
        )
    )
    return TestClient(app)


def claim(scope="discovery", nonce="nonce-1", issued_at="2026-09-19T20:29:00+00:00"):
    return {
        "agent_id": "agent-buyer-1",
        "key_id": "key-1",
        "nonce": nonce,
        "issued_at": issued_at,
        "signature": "sig-1",
        "requested_scope": scope,
    }


def test_health_reports_replay_guard_requirement():
    response = client().get("/v1/a2a-identity/health")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_authority"] == "none"
    assert body["configured"] is False


def test_unconfigured_verifier_fails_closed():
    response = client().post("/v1/a2a-identity/verify", json=claim())
    assert response.status_code == 503
    assert response.json()["detail"] == "a2a_identity_verifier_not_activated"


def test_valid_signature_grants_discovery_only():
    verifier = lambda key_id, payload, signature: (
        key_id == "key-1"
        and signature == "sig-1"
        and b"discovery" in payload
    )
    response = client(
        verifier,
        {"key-1"},
        InMemoryNonceRegistry(),
    ).post(
        "/v1/a2a-identity/verify",
        json=claim(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "discovery"
    assert body["execution_authority"] == "none"
    assert body["decision"]["authenticated"] is True


def test_nonce_replay_is_rejected():
    registry = InMemoryNonceRegistry()
    c = client(lambda *args: True, {"key-1"}, registry)
    first = c.post("/v1/a2a-identity/verify", json=claim())
    second = c.post("/v1/a2a-identity/verify", json=claim())
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["decision"]["authenticated"] is False
    assert second.json()["decision"]["reason"] == "nonce_replayed"


def test_expired_claim_is_rejected():
    response = client(
        lambda *args: True,
        {"key-1"},
        InMemoryNonceRegistry(),
    ).post(
        "/v1/a2a-identity/verify",
        json=claim(issued_at="2026-09-19T20:20:00+00:00"),
    )
    assert response.status_code == 200
    assert response.json()["decision"]["reason"] == "claim_expired"


def test_untrusted_key_is_rejected():
    response = client(
        lambda *args: True,
        {"another-key"},
        InMemoryNonceRegistry(),
    ).post(
        "/v1/a2a-identity/verify",
        json=claim(),
    )
    assert response.status_code == 200
    decision = response.json()["decision"]
    assert decision["authenticated"] is False
    assert decision["reason"] == "untrusted_key_id"


def test_commercial_execution_scope_is_rejected():
    response = client(
        lambda *args: True,
        {"key-1"},
        InMemoryNonceRegistry(),
    ).post(
        "/v1/a2a-identity/verify",
        json=claim("commerce.execute"),
    )
    assert response.status_code == 422
    assert "only discovery and commerce.intent scopes" in response.json()["detail"]
