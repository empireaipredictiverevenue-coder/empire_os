from fastapi.testclient import TestClient

from empire_os.resend_webhook_app import _receiving_api_key, create_app

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


def provider_event(event_type="email.delivered", *, permanent_bounce=False):
    data = {
        "email_id": "em_1",
        "from": "Phil <phil@mail.empire-ai.co.uk>",
        "to": ["buyer@example.com"],
        "subject": "Quick question",
        "tags": {"intent_id": INTENT},
        "created_at": "2026-09-18T12:00:00Z",
    }
    if event_type == "email.bounced":
        data["bounce"] = {
            "type": "Permanent" if permanent_bounce else "Temporary",
            "subType": "General",
        }
    return {"type": event_type, "data": data}



def test_receiving_api_key_prefers_dedicated_credential(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "send-only")
    monkeypatch.setenv("RESEND_RECEIVING_API_KEY", "receiving-capable")
    assert _receiving_api_key() == "receiving-capable"

    monkeypatch.delenv("RESEND_RECEIVING_API_KEY")
    assert _receiving_api_key() == "send-only"


def test_valid_signed_reply_ingests_only_inert_reply_record():
    calls = []
    def verify(_): return event()
    def rpc(name, params):
        calls.append((name, params))
        if name == "ingest_outbound_reply":
            return {"decision": "recorded", "reply_id": "00000000-0000-0000-0000-000000000099"}
        if name == "classify_outbound_reply":
            return {
                "decision": "classified",
                "classification": params["p_classification"],
                "suppressed": False,
            }
        raise AssertionError(name)
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
    assert calls[1][0] == "classify_outbound_reply"
    assert calls[1][1]["p_classification"] == "positive"
    assert r.json()["classification_auto_applied"] is True


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


def test_database_failure_is_retryable_and_non_actionable_event_is_ignored():
    failed = create_app(
        verify_webhook=lambda _: event(), fetch_email=lambda _: fetched(),
        reply_rpc=lambda *_: (_ for _ in ()).throw(RuntimeError("db down")),
        webhook_secret="whsec_test", reply_to="replies@empire-ai.co.uk",
    )
    r = TestClient(failed).post("/webhooks/resend-inbound", content="{}", headers=HEADERS)
    assert r.status_code == 503

    ignored = create_app(
        verify_webhook=lambda _: event("email.sent"),
        fetch_email=lambda _: (_ for _ in ()).throw(AssertionError("must not fetch")),
        reply_rpc=lambda *_: (_ for _ in ()).throw(AssertionError("must not write")),
        webhook_secret="whsec_test", reply_to="replies@empire-ai.co.uk",
    )
    r = TestClient(ignored).post("/webhooks/resend-inbound", content="{}", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["ignored"] is True


def test_provider_delivery_event_records_without_fetching_email():
    calls = []

    def rpc(name, params):
        calls.append((name, params))
        assert name == "record_outbound_provider_event"
        return {
            "decision": "recorded_provider_event",
            "event_type": params["p_event_type"],
            "suppressed": False,
        }

    app = create_app(
        verify_webhook=lambda _: provider_event("email.delivered"),
        fetch_email=lambda _: (_ for _ in ()).throw(AssertionError("must not fetch")),
        reply_rpc=rpc,
        webhook_secret="whsec_test",
        reply_to="replies@empire-ai.co.uk",
    )
    r = TestClient(app).post(
        "/webhooks/resend-inbound", content="{}", headers=HEADERS
    )
    assert r.status_code == 200
    assert r.json()["event_type"] == "delivered"
    assert calls[0][1]["p_intent_id"] == INTENT
    assert calls[0][1]["p_recipient"] == "buyer@example.com"


def test_permanent_bounce_requests_suppression():
    seen = {}

    def rpc(name, params):
        seen.update(params)
        return {
            "decision": "recorded_provider_event",
            "event_type": "bounced",
            "suppressed": True,
        }

    app = create_app(
        verify_webhook=lambda _: provider_event(
            "email.bounced", permanent_bounce=True
        ),
        fetch_email=lambda _: (_ for _ in ()).throw(AssertionError("must not fetch")),
        reply_rpc=rpc,
        webhook_secret="whsec_test",
        reply_to="replies@empire-ai.co.uk",
    )
    r = TestClient(app).post(
        "/webhooks/resend-inbound", content="{}", headers=HEADERS
    )
    assert r.status_code == 200
    assert seen["p_event_type"] == "bounced"
    assert seen["p_suppress"] is True
    assert r.json()["suppressed"] is True



class _ForwardEmails:
    sent = []

    @classmethod
    def send(cls, payload, options=None):
        cls.sent.append((payload, options))
        return {"id": "em_forward_test"}


class _ForwardResend:
    api_key = None
    Emails = _ForwardEmails


def test_governed_reply_is_ingested_and_mirrored_to_founder_gmail(
    monkeypatch,
):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    _ForwardEmails.sent = []
    calls = []

    def rpc(name, params):
        calls.append((name, params))
        if name == "ingest_outbound_reply":
            return {
                "decision": "recorded",
                "reply_id": (
                    "00000000-0000-0000-0000-000000000099"
                ),
            }
        if name == "classify_outbound_reply":
            return {
                "decision": "classified",
                "classification": params["p_classification"],
                "suppressed": False,
            }
        raise AssertionError(name)

    app = create_app(
        verify_webhook=lambda _: event(),
        fetch_email=lambda _: fetched(),
        reply_rpc=rpc,
        webhook_secret="whsec_test",
        reply_to="replies@empire-ai.co.uk",
        reply_forward_to="flavag83@gmail.com",
        reply_forward_sender=(
            "Phil - Founder - Empire AI "
            "<founder@empire-ai.co.uk>"
        ),
        resend_module=_ForwardResend,
    )
    r = TestClient(app).post(
        "/webhooks/resend-inbound",
        content="{}",
        headers=HEADERS,
    )

    assert r.status_code == 200
    assert r.json()["reply_forwarded"] is True
    assert r.json()["reply_forward_target"] == "flavag83@gmail.com"
    assert calls[0][0] == "ingest_outbound_reply"

    payload, options = _ForwardEmails.sent[0]
    assert payload["to"] == ["flavag83@gmail.com"]
    assert payload["from"] == (
        "Phil - Founder - Empire AI "
        "<founder@empire-ai.co.uk>"
    )
    assert payload["subject"].startswith("[Empire buyer reply]")
    assert "Interested, tell me more." in payload["text"]
    assert options["idempotency_key"] == "reply-forward/em_1"


def test_direct_founder_inbox_is_mirrored_without_reply_automation(
    monkeypatch,
):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    _ForwardEmails.sent = []

    direct_event = {
        "type": "email.received",
        "data": {
            "email_id": "em_founder_1",
            "from": "Sender <sender@example.com>",
            "received_for": ["founder@empire-ai.co.uk"],
            "to": ["founder@empire-ai.co.uk"],
            "subject": "Hello founder",
            "created_at": "2026-09-24T20:00:00Z",
        },
    }
    direct_fetched = {
        "from": "Sender <sender@example.com>",
        "subject": "Hello founder",
        "text": "Direct founder inbox message.",
        "received_for": ["founder@empire-ai.co.uk"],
        "headers": {},
    }

    app = create_app(
        verify_webhook=lambda _: direct_event,
        fetch_email=lambda _: direct_fetched,
        reply_rpc=lambda *_: (_ for _ in ()).throw(
            AssertionError("direct founder inbox must not enter reply RPC")
        ),
        webhook_secret="whsec_test",
        reply_to="reply@mail.empire-ai.co.uk",
        founder_inbox="founder@empire-ai.co.uk",
        reply_forward_to="flavag83@gmail.com",
        reply_forward_sender=(
            "Phil - Founder - Empire AI "
            "<founder@empire-ai.co.uk>"
        ),
        resend_module=_ForwardResend,
    )
    r = TestClient(app).post(
        "/webhooks/resend-inbound",
        content="{}",
        headers=HEADERS,
    )

    assert r.status_code == 200
    assert r.json()["ignored"] is True
    assert r.json()["reply_forwarded"] is True
    assert r.json()["reply_forward_target"] == "flavag83@gmail.com"

    payload, options = _ForwardEmails.sent[0]
    assert payload["subject"] == "[Empire inbox] Hello founder"
    assert "Direct founder inbox message." in payload["text"]
    assert options["idempotency_key"] == (
        "reply-forward/em_founder_1"
    )
