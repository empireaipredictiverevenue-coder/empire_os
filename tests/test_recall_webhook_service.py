import base64
import hashlib
import hmac

from fastapi.testclient import TestClient

import empire_os.recall_webhook_service as service
from empire_os.recall_verified_spool import FileRecallVerifiedSpool


def signed(raw: bytes):
    key = b"0123456789abcdef0123456789abcdef"
    secret = "whsec_" + base64.b64encode(key).decode("ascii")
    webhook_id = "msg_service_1"
    timestamp = "1790964000"
    signed_body = (
        webhook_id.encode() + b"." + timestamp.encode() + b"." + raw
    )
    signature = base64.b64encode(
        hmac.new(key, signed_body, hashlib.sha256).digest()
    ).decode("ascii")
    return secret, {
        "webhook-id": webhook_id,
        "webhook-timestamp": timestamp,
        "webhook-signature": f"v1,{signature}",
        "content-type": "application/json",
    }


def test_health_fails_closed_without_workspace_secret(monkeypatch):
    monkeypatch.delenv("RECALL_WORKSPACE_VERIFICATION_SECRET", raising=False)
    response = TestClient(service.app).get("/health")
    assert response.status_code == 503
    assert response.json()["workspace_verification_configured"] is False


def test_verified_request_reaches_private_spool(monkeypatch, tmp_path):
    raw = b'{"event":"transcript.data"}'
    secret, headers = signed(raw)
    monkeypatch.setenv("RECALL_WORKSPACE_VERIFICATION_SECRET", secret)
    monkeypatch.setattr(
        service,
        "SPOOL",
        FileRecallVerifiedSpool(tmp_path / "recall"),
    )

    response = TestClient(service.app).post(
        "/v1/providers/recall/realtime",
        content=raw,
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is True
    assert body["processed_inline"] is False
    assert len(list((tmp_path / "recall").glob("*.json"))) == 1


def test_service_rejects_unverified_request(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "RECALL_WORKSPACE_VERIFICATION_SECRET",
        "whsec_MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
    )
    monkeypatch.setattr(
        service,
        "SPOOL",
        FileRecallVerifiedSpool(tmp_path / "recall"),
    )
    response = TestClient(service.app).post(
        "/v1/providers/recall/realtime",
        content=b"{}",
        headers={
            "webhook-id": "bad",
            "webhook-timestamp": "1",
            "webhook-signature": "v1,AAAA",
        },
    )
    assert response.status_code == 401
    assert not (tmp_path / "recall").exists()
