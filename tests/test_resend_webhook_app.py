from fastapi.testclient import TestClient

from empire_os.resend_webhook_app import create_app

INTENT = "00000000-0000-0000-0000-000000000001"
HEADERS = {
    "svix-id": "msg_1",
    "svix-timestamp": "123",
    "svix-signature": "v1,test",
}


def event(event_type="email.received"):
    return {
        "type": event_type,
        "data": {
            "email_id": "em_1",
            "from": "Buyer <buyer@example.com>",
            "to": [f"replies+{INTENT}@empire-ai.co.uk"],
            "subject": "Re: proposal",
            "created_at": "2026-09-17T18:00:00Z",
        },
    }


def fetched(to=None):
    return {
        "from": "Buyer <buyer@example.com>",
        "subject": "Re: proposal",
        "text": "Interested, tell me more.",
        "received_for": to or [f"replies+{INTENT}@empire-ai.co.uk"],
        "headers": {"in-reply-to": "<original@example>"},
    }


def test_valid_signed_reply_ingests_only_inert_reply_record():
    calls = []
    def verify(_): return event()
    def rpc(name, params):
        calls.append((name, params))
        return {"decision": "recorded"}
    app = create_app(
        verify_webhook=verify, fetch_email=lambda _: fetched(), reply_rpc=rpc,
        webhook_secret="whsec_test", reply_to="replies@empire-ai.co.uk",
    )
    r = TestClient(app).post("/webhooks/resend-inbound", content="{}", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["decision"] == "recorded"
    assert calls[0][0] == "ingest_outbound_reply"
    params = calls[0][1]
    assert params["p_intent_id"] == INTENT
    assert params["p_metadata"]["untrusted_content"] is True
    assert params["p_body_text"] == "Interested, tell me more."


def test_bad_signature_is_400_and_unmatched_alias_is_ignored():
    bad = create_app(
        verify_webhook=lambda _: (_ for _ in ()).throw(ValueError("bad")),
        fetch_email=lambda _: fetched(), reply_rpc=lambda *_: None,
        webhook_secret="whsec_test", reply_to="replies@empire-ai.co.uk",
    )
    assert TestClient(bad).post("/webhooks/resend-inbound", content="{}", headers=HEADERS).status_code == 400

    calls = []
    unmatched = create_app(
        verify_webhook=lambda _: event(),
        fetch_email=lambda _: fetched(["other@empire-ai.co.uk"]),
        reply_rpc=lambda *args: calls.append(args),
        webhook_secret="whsec_test", reply_to="replies@empire-ai.co.uk",
    )
    r = TestClient(unmatched).post("/webhooks/resend-inbound", content="{}", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["ignored"] is True
    assert calls == []


def test_database_failure_is_retryable_and_non_received_event_is_ignored():
    failed = create_app(
        verify_webhook=lambda _: event(), fetch_email=lambda _: fetched(),
        reply_rpc=lambda *_: (_ for _ in ()).throw(RuntimeError("db down")),
        webhook_secret="whsec_test", reply_to="replies@empire-ai.co.uk",
    )
    r = TestClient(failed).post("/webhooks/resend-inbound", content="{}", headers=HEADERS)
    assert r.status_code == 503

    ignored = create_app(
        verify_webhook=lambda _: event("email.delivered"),
        fetch_email=lambda _: (_ for _ in ()).throw(AssertionError("must not fetch")),
        reply_rpc=lambda *_: (_ for _ in ()).throw(AssertionError("must not write")),
        webhook_secret="whsec_test", reply_to="replies@empire-ai.co.uk",
    )
    r = TestClient(ignored).post("/webhooks/resend-inbound", content="{}", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["ignored"] is True
