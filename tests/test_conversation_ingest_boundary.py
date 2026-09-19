from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from empire_os.conversation_api import create_conversation_router
from empire_os.conversation_transport import (
    ConversationTransportError,
    PostgresConversationIngestRpc,
    RpcConversationEventRepository,
)


class FakeRepository:
    def __init__(self):
        self.events = {}

    def append(self, *, provider, external_conversation_id, event):
        key = (event.conversation_id, event.provider_event_id)
        if key in self.events:
            return {
                "status": "existing",
                "event_id": self.events[key],
            }
        event_id = f"event-{len(self.events) + 1}"
        self.events[key] = event_id
        return {"status": "recorded", "event_id": event_id}


def client(repository=None):
    app = FastAPI()
    app.include_router(create_conversation_router(repository))
    return TestClient(app)


def vonage_payload():
    return {
        "provider": "vonage",
        "conversation_id": "conversation-1",
        "payload": {
            "conversation_uuid": "vonage-conv-1",
            "event_uuid": "provider-event-1",
            "event_type": "speech_received",
            "timestamp": "2026-09-19T20:45:00+00:00",
            "direction": "inbound",
            "text": "Interested",
            "actor": "buyer",
        },
    }


def test_unbound_ingest_fails_closed():
    response = client().post(
        "/v1/conversations/events/ingest",
        json=vonage_payload(),
    )
    assert response.status_code == 503
    assert response.json()["detail"] == (
        "conversation_provider_ingest_not_activated"
    )


def test_provider_event_appends_without_execution_authority():
    repo = FakeRepository()
    response = client(repo).post(
        "/v1/conversations/events/ingest",
        json=vonage_payload(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "recorded"
    assert body["write_authority"] == "append_only_event"
    assert body["provider_activation"] is False
    assert body["execution_authority"] == "none"
    assert body["outbound_calls"] is False
    assert body["voice_streaming"] is False
    assert body["email_sends"] is False
    assert body["booking_execution"] is False


def test_provider_event_is_idempotent():
    repo = FakeRepository()
    c = client(repo)
    first = c.post(
        "/v1/conversations/events/ingest",
        json=vonage_payload(),
    )
    second = c.post(
        "/v1/conversations/events/ingest",
        json=vonage_payload(),
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "existing"
    assert len(repo.events) == 1


def test_rpc_repository_maps_canonical_event():
    calls = []

    def rpc(name, params):
        calls.append((name, params))
        return {
            "status": "recorded",
            "event_id": "event-1",
        }

    repo = RpcConversationEventRepository(rpc)
    preview_app = FastAPI()
    preview_app.include_router(create_conversation_router(repo))
    response = TestClient(preview_app).post(
        "/v1/conversations/events/ingest",
        json=vonage_payload(),
    )
    assert response.status_code == 200
    assert calls[0][0] == "ingest_conversation_provider_event"
    assert calls[0][1]["p_provider"] == "vonage"
    assert calls[0][1]["p_provider_event_id"] == "provider-event-1"


def test_transport_rejects_non_ingest_rpc_before_connect():
    rpc = PostgresConversationIngestRpc(
        "postgresql://example",
        connect_factory=lambda dsn: (_ for _ in ()).throw(
            AssertionError("must not connect")
        ),
    )
    with pytest.raises(
        ConversationTransportError,
        match="cannot execute",
    ):
        rpc("send_conversation_message", {})
