"""Inbound body-fetch failures must carry only non-sensitive diagnostics."""
from __future__ import annotations

import pytest
from empire_os.outbound_provider import inbound_fetch_error_code, extract_resend_reply
from empire_os.resend_webhook_app import create_app
from fastapi.testclient import TestClient

INTENT = "c77e459a-c3a9-4b0a-962a-e52c0f728bd9"


class FakeProviderException(Exception):
    def __init__(self, status_code, message="secret key re_should_not_leak"):
        super().__init__(message)
        self.status_code = status_code


@pytest.mark.parametrize("status, expected", [
    (401, "RECEIVING_CREDENTIAL_UNAUTHORIZED"),
    (403, "RECEIVING_ACCESS_FORBIDDEN"),
    (404, "RECEIVED_MESSAGE_NOT_FOUND"),
    (429, "RECEIVING_RATE_LIMITED"),
    (502, "RECEIVING_PROVIDER_UNAVAILABLE"),
    (None, "RECEIVING_FETCH_FAILED_UNKNOWN"),
])
def test_status_codes_without_provider_secrets(status, expected):
    e = FakeProviderException(status)
    result = inbound_fetch_error_code(e)
    assert result == expected
    assert "secret" not in result


def test_network_timeout_is_sanitized():
    assert inbound_fetch_error_code(TimeoutError("PRIVATE DETAILS")) == "RECEIVING_NETWORK_FAILURE"


def test_fallback_reply_keeps_safe_failure_code_not_raw_api_error():
    event = {
        "type": "email.received",
        "data": {
            "email_id": "provider-existing-id",
            "from": "buyer@example.org",
            "to": [f"reply+{INTENT}@mail.empire-ai.co.uk"],
            "subject": "Re: a question",
            "created_at": "2026-09-23T00:48:08.417Z",
        },
    }
    def denied(_):
        raise FakeProviderException(403)
    reply = extract_resend_reply(
        event, fetch_email=denied, reply_to="reply@mail.empire-ai.co.uk"
    )
    assert reply["body_unavailable"] is True
    assert reply["body_fetch_error_code"] == "RECEIVING_ACCESS_FORBIDDEN"
    assert reply["body_text"] == "[provider body unavailable]"
    assert reply["untrusted_content"] is True
    assert reply["executable"] is False


def test_webhook_persists_safe_diagnostic_metadata_and_does_not_send():
    event = {
        "type": "email.received",
        "data": {
            "email_id": "provider-existing-id",
            "from": "buyer@example.org",
            "to": [f"reply+{INTENT}@mail.empire-ai.co.uk"],
            "subject": "Re: a question",
            "created_at": "2026-09-23T00:48:08.417Z",
        },
    }
    calls = []
    def record(name, params):
        calls.append((name, params))
        assert name == "ingest_outbound_reply"
        return {"decision":"recorded", "reply_id":"11111111-1111-4111-8111-111111111111"}
    app = create_app(
        verify_webhook=lambda *_a, **_kw: event,
        fetch_email=lambda _: (_ for _ in ()).throw(FakeProviderException(401)),
        reply_rpc=record,
        webhook_secret="dummy-signed-test-secret",
        reply_to="reply@mail.empire-ai.co.uk",
    )
    response = TestClient(app).post(
        "/webhooks/resend-inbound", content="{}",
        headers={
            "svix-id": "msg_1",
            "svix-timestamp": "123",
            "svix-signature": "v1,test",
        },
    )
    assert response.status_code == 200
    assert len(calls) == 1
    metadata = calls[0][1]["p_metadata"]
    assert metadata["body_fetch_error_code"] == "RECEIVING_CREDENTIAL_UNAUTHORIZED"
    assert metadata["body_unavailable"] is True
    assert "secret" not in str(metadata).lower()
