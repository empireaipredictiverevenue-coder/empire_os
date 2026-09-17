import pytest

from empire_os.outbound_provider import (
    OutboundProviderError,
    build_resend_send,
    extract_resend_reply,
    verify_resend_inbound,
)


def authorized_claim(**overrides):
    value = {
        "decision": "authorized_send",
        "intent_id": "00000000-0000-0000-0000-000000000001",
        "channel": "email",
        "recipient": "Buyer@Example.com",
        "subject": "Empire test",
        "body_text": "Plain text body",
        "body_html": "<p>Plain text body</p>",
        "actual_revenue": False,
    }
    value.update(overrides)
    return value


def test_send_payload_requires_database_authorized_claim():
    payload = build_resend_send(
        authorized_claim(), sender="Empire <sales@empire-ai.co.uk>",
        reply_to="replies@empire-ai.co.uk",
    )
    assert payload["to"] == ["buyer@example.com"]
    assert payload["tags"][0]["value"].endswith("0001")
    with pytest.raises(OutboundProviderError, match="authorized"):
        build_resend_send({}, sender="a@example.com", reply_to="b@example.com")


def test_webhook_verification_requires_signed_headers_and_rejects_failure():
    event = {"type": "email.received", "data": {"email_id": "em_1"}}
    seen = {}
    def verify_webhook(**kwargs):
        seen.update(kwargs)
        return event
    value = verify_resend_inbound(
        '{"type":"email.received"}',
        {"svix-id":"id","svix-timestamp":"ts","svix-signature":"sig"},
        secret="whsec_test", verify_webhook=verify_webhook,
    )
    assert value == event
    assert seen["secret"] == "whsec_test"
    with pytest.raises(OutboundProviderError, match="headers"):
        verify_resend_inbound("{}", {}, secret="x", verify_webhook=verify_webhook)
    with pytest.raises(OutboundProviderError, match="verification failed"):
        verify_resend_inbound("{}", {"svix-id":"i","svix-timestamp":"t","svix-signature":"s"},
                              secret="x", verify_webhook=lambda **_: (_ for _ in ()).throw(ValueError()))


def test_extract_reply_returns_inert_plain_text_only():
    event = {"type":"email.received","data":{"email_id":"em_1","from":"buyer@example.com","created_at":"2026-09-17T18:00:00Z"}}
    reply = extract_resend_reply(event, fetch_email=lambda _: {"data": {
        "from":"Buyer <buyer@example.com>", "subject":"Re: hello", "text":"Interested",
        "headers":{"in-reply-to":"<orig@example>"}
    }})
    assert reply["from_contact"] == "buyer@example.com"
    assert reply["body_text"] == "Interested"
    assert reply["untrusted_content"] is True
    assert reply["executable"] is False
    assert reply["in_reply_to"] == "<orig@example>"


def test_extract_reply_ignores_non_email_event_and_rejects_html_only():
    assert extract_resend_reply({"type":"email.delivered"}, fetch_email=lambda _: {}) is None
    with pytest.raises(OutboundProviderError, match="plain-text"):
        extract_resend_reply(
            {"type":"email.received","data":{"email_id":"em_2","from":"buyer@example.com"}},
            fetch_email=lambda _: {"data":{"from":"buyer@example.com","html":"<p>hi</p>"}},
        )


def test_send_payload_rejects_non_email_and_revenue_claims():
    with pytest.raises(OutboundProviderError, match="safe email"):
        build_resend_send(authorized_claim(channel="sms"), sender="a@example.com", reply_to="b@example.com")
    with pytest.raises(OutboundProviderError, match="safe email"):
        build_resend_send(authorized_claim(actual_revenue=True), sender="a@example.com", reply_to="b@example.com")


def test_send_with_resend_uses_validated_payload_and_requires_message_id():
    class Emails:
        @staticmethod
        def send(payload):
            assert payload["to"] == ["buyer@example.com"]
            assert "_sender_address" not in payload
            return {"id":"em_test_123"}
    class FakeResend:
        api_key = None
    FakeResend.Emails = Emails
    from empire_os.outbound_provider import send_with_resend
    payload = build_resend_send(
        authorized_claim(), sender="Empire <sales@empire-ai.co.uk>",
        reply_to="replies@empire-ai.co.uk",
    )
    assert send_with_resend(payload, api_key="re_test", resend_module=FakeResend) == "em_test_123"
    assert FakeResend.api_key == "re_test"
    with pytest.raises(OutboundProviderError, match="API key"):
        send_with_resend(payload, api_key="", resend_module=FakeResend)
