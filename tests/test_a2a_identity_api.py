from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.a2a_identity_api import create_a2a_identity_router


def client(verifier=None, trusted=None):
    app = FastAPI()
    app.include_router(
        create_a2a_identity_router(
            verifier=verifier,
            trusted_key_ids=trusted,
        )
    )
    return TestClient(app)


def claim(scope="discovery"):
    return {
        "agent_id": "agent-buyer-1",
        "key_id": "key-1",
        "nonce": "nonce-1",
        "issued_at": "2026-09-19T19:15:00+00:00",
        "signature": "sig-1",
        "requested_scope": scope,
    }


def test_health_is_discovery_only():
    response = client().get("/v1/a2a-identity/health")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["scope"] == "discovery"
    assert body["execution_authority"] == "none"
    assert body["commerce_execution"] is False
    assert body["payment_execution"] is False
    assert body["allocation_execution"] is False
    assert body["configured"] is False


def test_unconfigured_verifier_fails_closed():
    response = client().post("/v1/a2a-identity/verify", json=claim())
    assert response.status_code == 503
    assert (
        response.json()["detail"]
        == "a2a_identity_verifier_not_activated"
    )


def test_valid_signature_grants_discovery_only():
    verifier = lambda key_id, payload, signature: (
        key_id == "key-1"
        and signature == "sig-1"
        and b"discovery" in payload
    )
    response = client(verifier, {"key-1"}).post(
        "/v1/a2a-identity/verify",
        json=claim(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "discovery"
    assert body["execution_authority"] == "none"
    decision = body["decision"]
    assert decision["authenticated"] is True
    assert decision["granted_scope"] == "discovery"
    assert decision["execution_authority"] == "none"


def test_untrusted_key_is_rejected():
    response = client(
        lambda *args: True,
        {"another-key"},
    ).post(
        "/v1/a2a-identity/verify",
        json=claim(),
    )
    assert response.status_code == 200
    decision = response.json()["decision"]
    assert decision["authenticated"] is False
    assert decision["reason"] == "untrusted_key_id"


def test_commercial_scope_is_rejected():
    response = client(
        lambda *args: True,
        {"key-1"},
    ).post(
        "/v1/a2a-identity/verify",
        json=claim("commerce.execute"),
    )
    assert response.status_code == 422
    assert "only discovery scope is supported" in response.json()["detail"]
