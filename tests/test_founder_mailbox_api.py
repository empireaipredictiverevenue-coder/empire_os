from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.founder_mailbox_api import (
    ResendMailboxProvider,
    create_founder_mailbox_router,
    read_mail_identity,
)


class FakeProvider:
    def list_sent(self, *, limit):
        return [{
            "id": "sent-1",
            "to": ["buyer@example.com"],
            "reply_to": ["reply+11111111-2222-3333-4444-555555555555@mail.empire-ai.co.uk"],
            "subject": "Pilot",
            "created_at": "2026-09-25T10:00:00+00:00",
            "last_event": "delivered",
        }]

    def list_received(self, *, limit):
        return [{
            "id": "in-1",
            "from": "buyer@example.com",
            "to": ["reply+11111111-2222-3333-4444-555555555555@mail.empire-ai.co.uk"],
            "subject": "Re: Pilot",
            "received_at": "2026-09-25T11:00:00+00:00",
            "text": "Can you send more?",
        }]

    def list_suppressions(self, *, limit):
        return []

    def get_sent(self, email_id):
        return {"text": "Original message", "message_id": "<sent@example>"}

    def get_received(self, email_id):
        return {"text": "Can you send more?", "message_id": "<reply@example>"}


def app():
    value = FastAPI()
    value.include_router(create_founder_mailbox_router(FakeProvider()))
    return value


def test_mailbox_api_is_read_only_and_exposes_threads():
    client = TestClient(app())
    response = client.get("/v1/founder-mailbox/threads")
    assert response.status_code == 200
    payload = response.json()
    assert payload["read_only"] is True
    assert payload["execution_authority"] == "none"
    assert payload["summary"]["replies"] == 1
    assert payload["threads"][0]["classification"] == "positive"
    assert "events" not in payload["threads"][0]


def test_mailbox_thread_detail_contains_plain_text_timeline_without_send_authority():
    client = TestClient(app())
    thread_id = "11111111-2222-3333-4444-555555555555"
    response = client.get(f"/v1/founder-mailbox/threads/{thread_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["email_sends"] is False
    assert payload["execution_authority"] == "none"
    assert len(payload["events"]) == 2
    assert payload["events"][0]["untrusted_content"] is True

def test_mail_identity_reads_only_safe_keys(tmp_path, monkeypatch):
    monkeypatch.delenv("EMPIRE_OUTBOUND_FROM", raising=False)
    monkeypatch.delenv("EMPIRE_REPLY_TO", raising=False)
    path = tmp_path / "outbound.env"
    path.write_text(
        'EMPIRE_OUTBOUND_FROM="Phil - Founder - Empire AI <phil@mail.empire-ai.co.uk>"\n'
        'EMPIRE_REPLY_TO=reply@mail.empire-ai.co.uk\n'
        'RESEND_API_KEY=secret-never-exposed\n',
        encoding="utf-8",
    )
    identity = read_mail_identity(path)
    assert identity == {
        "sender": "Phil - Founder - Empire AI <phil@mail.empire-ai.co.uk>",
        "sender_email": "phil@mail.empire-ai.co.uk",
        "reply_to": "reply@mail.empire-ai.co.uk",
        "observed": True,
    }
    assert "secret" not in str(identity).lower()

def test_resend_provider_loads_only_required_keys_from_runtime_file(
    tmp_path,
    monkeypatch,
):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("RESEND_RECEIVING_API_KEY", raising=False)
    path = tmp_path / "outbound.env"
    path.write_text(
        "RESEND_API_KEY=send-key\n"
        "RESEND_RECEIVING_API_KEY=receive-key\n"
        "EMPIRE_OUTBOUND_SENDER_DSN=must-not-be-loaded\n",
        encoding="utf-8",
    )
    provider = ResendMailboxProvider(secret_env_path=path)
    assert provider.sending_api_key == "send-key"
    assert provider.receiving_api_key == "receive-key"
    assert not hasattr(provider, "sender_dsn")

def test_mailbox_draft_preview_uses_existing_closer_logic():
    client = TestClient(app())
    thread_id = "11111111-2222-3333-4444-555555555555"
    response = client.get(
        "/v1/founder-mailbox/draft-preview",
        params={"thread_id": thread_id},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["outbound_send_authority"] is False
    assert payload["execution_authority"] == "none"
    assert payload["classification"] == "positive"
    assert payload["unknowns_preserved"] is True
    assert payload["draft"]["subject"].startswith("Re:")
    assert "Best," in payload["draft"]["body_text"]


def test_mailbox_draft_preview_fails_closed_without_inbound_reply():
    class NoReplyProvider(FakeProvider):
        def list_received(self, *, limit):
            return []

    value = FastAPI()
    value.include_router(create_founder_mailbox_router(NoReplyProvider()))
    client = TestClient(value)
    response = client.get(
        "/v1/founder-mailbox/draft-preview",
        params={"thread_id": "11111111-2222-3333-4444-555555555555"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "inbound_reply_required"


def test_mailbox_draft_preview_fails_closed_for_suppressed_recipient():
    class SuppressedProvider(FakeProvider):
        def list_suppressions(self, *, limit):
            return [{
                "id": "sup-1",
                "email": "buyer@example.com",
                "origin": "manual",
            }]

    value = FastAPI()
    value.include_router(create_founder_mailbox_router(SuppressedProvider()))
    client = TestClient(value)
    response = client.get(
        "/v1/founder-mailbox/draft-preview",
        params={"thread_id": "11111111-2222-3333-4444-555555555555"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "recipient_suppressed"



def test_resend_provider_lists_suppressions(monkeypatch):
    provider = ResendMailboxProvider(
        api_key="send-key",
        receiving_api_key="receive-key",
    )
    calls = []

    def fake_get(path, *, params=None, receiving=False, mailbox=False):
        calls.append((path, params, receiving, mailbox))
        return {
            "object": "list",
            "data": [{
                "id": "sup-1",
                "email": "buyer@example.com",
                "origin": "manual",
            }],
        }

    monkeypatch.setattr(provider, "_get", fake_get)

    rows = provider.list_suppressions(limit=25)

    assert rows == [{
        "id": "sup-1",
        "email": "buyer@example.com",
        "origin": "manual",
    }]
    assert calls == [
        ("/suppressions", {"limit": 25}, False, True)
    ]

def test_resend_provider_uses_separate_mailbox_key(monkeypatch):
    provider = ResendMailboxProvider(
        api_key="send-key",
        receiving_api_key="receive-key",
        mailbox_api_key="mailbox-key",
    )

    calls = []

    class Response:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_requests_get(
        url,
        *,
        params=None,
        headers=None,
        timeout=None,
    ):
        calls.append({
            "url": url,
            "params": params,
            "authorization": headers.get("Authorization"),
        })
        return Response({"data": []})

    monkeypatch.setattr(
        "empire_os.founder_mailbox_api.requests.get",
        fake_requests_get,
    )

    provider.list_sent(limit=5)
    provider.list_suppressions(limit=5)
    provider.list_received(limit=5)

    assert calls[0]["authorization"] == "Bearer mailbox-key"
    assert calls[1]["authorization"] == "Bearer mailbox-key"
    assert calls[2]["authorization"] == "Bearer receive-key"
