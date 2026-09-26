from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from empire_os.a2a_commerce_api import create_a2a_commerce_router
from empire_os.a2a_commerce_intent import (
    CommercialIntent,
    normalize_intent_record,
)
from empire_os.a2a_commerce_transport import (
    A2ACommerceTransportError,
    PostgresA2AIntentRpc,
    RpcCommercialIntentRepository,
)
from empire_os.a2a_identity import InMemoryNonceRegistry


NOW = datetime(2026, 9, 19, 20, 30, tzinfo=timezone.utc)


class FakeRepository:
    def __init__(self):
        self.rows = {}

    def record(self, *, intent: CommercialIntent):
        intent.validate()
        existing = self.rows.get(intent.idempotency_key)
        if existing:
            return {**existing, "status": "existing"}
        row = {
            "status": "pending_approval",
            "intent_id": f"intent-{len(self.rows) + 1}",
            "agent_id": intent.agent_id,
            "capability": intent.capability,
        }
        self.rows[intent.idempotency_key] = row
        return row


def api_client(repository=None, verifier=None, trusted=None, registry=None):
    app = FastAPI()
    app.include_router(
        create_a2a_commerce_router(
            repository=repository,
            verifier=verifier,
            trusted_key_ids=trusted,
            nonce_registry=registry,
            clock=lambda: NOW,
        )
    )
    return TestClient(app)


def request_body(
    idempotency_key="intent-key-1",
    nonce="nonce-1",
    issued_at="2026-09-19T20:29:00+00:00",
):
    return {
        "identity": {
            "agent_id": "agent-buyer-1",
            "key_id": "key-1",
            "nonce": nonce,
            "issued_at": issued_at,
            "signature": "sig-1",
        },
        "capability": "commerce.quote.request",
        "idempotency_key": idempotency_key,
        "request": {"product": "lead-intelligence"},
        "evidence": {"source": "agent_request"},
    }


def valid_verifier(key_id, payload, signature):
    return (
        key_id == "key-1"
        and signature == "sig-1"
        and b"commerce.intent" in payload
    )


def configured_client(repo=None, registry=None):
    return api_client(
        repo or FakeRepository(),
        valid_verifier,
        {"key-1"},
        registry or InMemoryNonceRegistry(),
    )


def test_unbound_commerce_api_fails_closed():
    client = api_client()
    health = client.get("/v1/a2a-commerce/health")
    assert health.status_code == 200
    assert health.json()["configured"] is False
    response = client.post(
        "/v1/a2a-commerce/intents",
        json=request_body(),
    )
    assert response.status_code == 503


def test_authenticated_intent_is_pending_approval_only():
    repo = FakeRepository()
    client = configured_client(repo)
    response = client.post(
        "/v1/a2a-commerce/intents",
        json=request_body(),
    )
    assert response.status_code == 200
    body = response.json()
    decision = body["decision"]
    assert decision["status"] == "pending_approval"
    assert decision["human_approval_required"] is True
    assert decision["execution_authority"] == "none"
    assert decision["payment_authority"] is False
    assert decision["allocation_authority"] is False
    assert body["execution_authority"] == "none"


def test_duplicate_intent_is_idempotent_with_new_nonce():
    repo = FakeRepository()
    client = configured_client(repo)
    first = client.post(
        "/v1/a2a-commerce/intents",
        json=request_body(nonce="nonce-1"),
    )
    second = client.post(
        "/v1/a2a-commerce/intents",
        json=request_body(nonce="nonce-2"),
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["decision"]["status"] == "existing"
    assert len(repo.rows) == 1


def test_replayed_nonce_is_rejected_before_repository():
    repo = FakeRepository()
    registry = InMemoryNonceRegistry()
    client = configured_client(repo, registry)
    first = client.post(
        "/v1/a2a-commerce/intents",
        json=request_body(nonce="nonce-1"),
    )
    second = client.post(
        "/v1/a2a-commerce/intents",
        json=request_body(
            idempotency_key="intent-key-2",
            nonce="nonce-1",
        ),
    )
    assert first.status_code == 200
    assert second.status_code == 401
    assert second.json()["detail"] == "nonce_replayed"
    assert len(repo.rows) == 1


def test_expired_identity_claim_is_rejected():
    client = configured_client()
    response = client.post(
        "/v1/a2a-commerce/intents",
        json=request_body(issued_at="2026-09-19T20:20:00+00:00"),
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "claim_expired"


def test_invalid_signature_is_rejected():
    client = api_client(
        FakeRepository(),
        lambda *args: False,
        {"key-1"},
        InMemoryNonceRegistry(),
    )
    response = client.post(
        "/v1/a2a-commerce/intents",
        json=request_body(),
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "signature_invalid"


def test_unsupported_capability_rejected():
    repo = FakeRepository()
    client = configured_client(repo)
    body = request_body()
    body["capability"] = "commerce.payment.execute"
    response = client.post("/v1/a2a-commerce/intents", json=body)
    assert response.status_code == 422


def test_normalizer_rejects_executed_status():
    with pytest.raises(ValueError, match="unexpected commercial intent status"):
        normalize_intent_record({
            "status": "executed",
            "intent_id": "i1",
            "agent_id": "a1",
            "capability": "commerce.task.create",
        })


def test_rpc_repository_maps_intent_to_single_allowed_rpc():
    calls = []

    def rpc(name, params):
        calls.append((name, params))
        return {
            "status": "pending_approval",
            "intent_id": "i1",
            "agent_id": "a1",
            "capability": "commerce.task.create",
        }

    repo = RpcCommercialIntentRepository(rpc)
    result = repo.record(
        intent=CommercialIntent(
            agent_id="a1",
            key_id="k1",
            identity_nonce="nonce-1",
            identity_issued_at="2026-09-19T20:29:00+00:00",
            capability="commerce.task.create",
            idempotency_key="idem-1",
            request={"task": "review"},
            evidence={"source": "test"},
        )
    )
    assert result["status"] == "pending_approval"
    assert calls[0][0] == "record_a2a_commercial_intent"


def test_postgres_transport_rejects_any_other_rpc_before_connect():
    rpc = PostgresA2AIntentRpc(
        "postgresql://example",
        connect_factory=lambda dsn: (_ for _ in ()).throw(
            AssertionError("must not connect")
        ),
    )
    with pytest.raises(
        A2ACommerceTransportError,
        match="cannot execute",
    ):
        rpc("approve_a2a_commercial_intent", {})
