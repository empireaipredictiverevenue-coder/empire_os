from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.conversation_api import create_conversation_router


def client():
    app = FastAPI()
    app.include_router(create_conversation_router())
    return TestClient(app)


def test_health_has_no_provider_execution():
    response = client().get("/v1/conversations/health")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_authority"] == "none"
    assert body["provider_activation"] is False
    assert body["outbound_calls"] is False
    assert body["voice_streaming"] is False
    assert body["email_sends"] is False
    assert body["booking_execution"] is False


def test_vonage_event_preview_normalises_to_canonical_event():
    response = client().post(
        "/v1/conversations/events/preview",
        json={
            "provider": "vonage",
            "conversation_id": "conversation-1",
            "payload": {
                "conversation_uuid": "vonage-conv-1",
                "event_uuid": "event-1",
                "event_type": "speech_received",
                "timestamp": "2026-09-19T19:05:00+00:00",
                "direction": "inbound",
                "text": "Interested",
                "actor": "buyer",
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["provider_activation"] is False
    assert body["write_authority"] == "none"
    assert body["provider_event"]["provider"] == "vonage"
    assert body["canonical_event"]["conversation_id"] == "conversation-1"
    assert body["canonical_event"]["direction"] == "inbound"
    assert body["canonical_event"]["text"] == "Interested"


def test_elevenlabs_preview_does_not_stream():
    response = client().post(
        "/v1/conversations/events/preview",
        json={
            "provider": "elevenlabs",
            "conversation_id": "conversation-2",
            "payload": {
                "conversation_id": "el-1",
                "event_id": "el-event-1",
                "event_type": "transcript_segment",
                "occurred_at": "2026-09-19T19:06:00+00:00",
                "direction": "outbound",
                "transcript_text": "How can I help?",
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["canonical_event"]["text"] == "How can I help?"


def test_unknown_provider_fails_closed():
    response = client().post(
        "/v1/conversations/events/preview",
        json={
            "provider": "twilio",
            "conversation_id": "conversation-1",
            "payload": {},
        },
    )
    assert response.status_code == 422
    assert "unsupported conversation provider" in response.json()["detail"]


def test_missing_canonical_conversation_id_is_rejected():
    response = client().post(
        "/v1/conversations/events/preview",
        json={
            "provider": "email",
            "conversation_id": "",
            "payload": {
                "thread_id": "thread-1",
                "message_id": "message-1",
                "event_type": "reply_received",
                "occurred_at": "2026-09-19T19:07:00+00:00",
                "direction": "inbound",
                "body_text": "Send more info",
            },
        },
    )
    assert response.status_code == 422
    assert "canonical conversation_id required" in response.json()["detail"]
