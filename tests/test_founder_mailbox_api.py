from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.founder_mailbox_api import (
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

