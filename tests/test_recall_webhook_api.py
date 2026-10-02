import base64
import hashlib
import hmac

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.recall_webhook_api import create_recall_webhook_router


def signed_headers(raw: bytes):
    key = b"0123456789abcdef0123456789abcdef"
    secret = "whsec_" + base64.b64encode(key).decode("ascii")
    webhook_id = "msg_test_api"
    timestamp = "1790964000"
    signed = (
        webhook_id.encode()
        + b"."
        + timestamp.encode()
        + b"."
        + raw
    )
    signature = base64.b64encode(
        hmac.new(key, signed, hashlib.sha256).digest()
    ).decode("ascii")
    return secret, {
        "webhook-id": webhook_id,
        "webhook-timestamp": timestamp,
        "webhook-signature": f"v1,{signature}",
        "content-type": "application/json",
    }


def client(secret_provider, sink):
    app = FastAPI()
    app.include_router(
        create_recall_webhook_router(
            secret_provider=secret_provider,
            verified_envelope_sink=sink,
        )
    )
    return TestClient(app)


def test_verified_request_is_enqueued_not_processed_inline():
    raw = b'{"event":"transcript.data"}'
    secret, headers = signed_headers(raw)
    accepted = []
    response = client(lambda: secret, accepted.append).post(
        "/v1/providers/recall/realtime",
        content=raw,
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is True
    assert body["verified"] is True
    assert body["processed_inline"] is False
    assert body["execution_authority"] == "none"
    assert len(accepted) == 1
    assert accepted[0].raw_payload == raw
    assert accepted[0].verification.verified is True
    assert accepted[0].received_at == "2026-10-02T18:00:00+00:00"


def test_invalid_signature_is_rejected_before_sink():
    raw = b'{"event":"transcript.data"}'
    secret, headers = signed_headers(raw)
    headers["webhook-signature"] = "v1,AAAA"
    accepted = []
    response = client(lambda: secret, accepted.append).post(
        "/v1/providers/recall/realtime",
        content=raw,
        headers=headers,
    )
    assert response.status_code == 401
    assert accepted == []


def test_missing_secret_fails_closed():
    response = client(lambda: "", lambda envelope: None).post(
        "/v1/providers/recall/realtime",
        content=b"{}",
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "recall_verification_secret_unavailable"


def test_queue_failure_returns_retryable_error():
    raw = b'{"event":"transcript.data"}'
    secret, headers = signed_headers(raw)

    def broken_sink(_envelope):
        raise RuntimeError("queue down")

    response = client(lambda: secret, broken_sink).post(
        "/v1/providers/recall/realtime",
        content=raw,
        headers=headers,
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "recall_verified_event_queue_unavailable"
