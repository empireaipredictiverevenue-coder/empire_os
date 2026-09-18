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
        "body_text": "Plain text body. Reply opt out. 31 St Thomas St, Bolton, BL1 2QR, UK",
        "body_html": "<p>Plain text body</p>",
        "actual_revenue": False,
    }
    value.update(overrides)
    return value


def test_send_payload_requires_database_authorized_claim():
    payload = build_resend_send(
        authorized_claim(), sender="Phil - Founder - Empire AI <phil@mail.empire-ai.co.uk>",
        reply_to="reply@mail.empire-ai.co.uk",
    )
    assert payload["to"] == ["buyer@example.com"]
    assert payload["tags"][0]["value"].endswith("0001")
    with pytest.raises(OutboundProviderError, match="authorized"):
        build_resend_send({}, sender="a@mail.empire-ai.co.uk", reply_to="b@mail.empire-ai.co.uk")


def test_webhook_verification_requires_signed_headers_and_rejects_failure():
    event = {"type": "email.received", "data": {"email_id": "em_1"}}
    seen = {}
    def verify_webhook(options):
        seen.update(options)
        return event
    value = verify_resend_inbound(
        '{"type":"email.received"}',
        {"svix-id":"id","svix-timestamp":"ts","svix-signature":"sig"},
        secret="whsec_test", verify_webhook=verify_webhook,
    )
    assert value == event
    assert seen["webhook_secret"] == "whsec_test"
    assert seen["headers"] == {"id":"id","timestamp":"ts","signature":"sig"}
    with pytest.raises(OutboundProviderError, match="headers"):
        verify_resend_inbound("{}", {}, secret="x", verify_webhook=verify_webhook)
    with pytest.raises(OutboundProviderError, match="verification failed"):
        verify_resend_inbound("{}", {"svix-id":"i","svix-timestamp":"t","svix-signature":"s"},
                              secret="x", verify_webhook=lambda _: (_ for _ in ()).throw(ValueError()))


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
        build_resend_send(authorized_claim(channel="sms"), sender="a@mail.empire-ai.co.uk", reply_to="b@mail.empire-ai.co.uk")
    with pytest.raises(OutboundProviderError, match="safe email"):
        build_resend_send(authorized_claim(actual_revenue=True), sender="a@mail.empire-ai.co.uk", reply_to="b@mail.empire-ai.co.uk")


def test_send_with_resend_uses_validated_payload_and_requires_message_id():
    class Emails:
        @staticmethod
        def send(payload, options=None):
            assert payload["to"] == ["buyer@example.com"]
            assert "_sender_address" not in payload
            assert options == {"idempotency_key":"outbound/00000000-0000-0000-0000-000000000001"}
            return {"id":"em_test_123"}
    class FakeResend:
        api_key = None
    FakeResend.Emails = Emails
    from empire_os.outbound_provider import send_with_resend
    payload = build_resend_send(
        authorized_claim(), sender="Phil - Founder - Empire AI <phil@mail.empire-ai.co.uk>",
        reply_to="reply@mail.empire-ai.co.uk",
    )
    assert send_with_resend(payload, api_key="re_test", resend_module=FakeResend) == "em_test_123"
    assert FakeResend.api_key == "re_test"
    with pytest.raises(OutboundProviderError, match="API key"):
        send_with_resend(payload, api_key="", resend_module=FakeResend)


def test_send_payload_uses_intent_specific_reply_alias():
    payload = build_resend_send(
        authorized_claim(), sender="Phil - Founder - Empire AI <phil@mail.empire-ai.co.uk>",
        reply_to="reply@mail.empire-ai.co.uk",
    )
    assert payload["reply_to"] == [
        "reply+00000000-0000-0000-0000-000000000001@mail.empire-ai.co.uk"
    ]
    from empire_os.outbound_provider import resolve_intent_from_recipients
    resolved = resolve_intent_from_recipients(
        payload["reply_to"], reply_to="reply@mail.empire-ai.co.uk",
    )
    assert resolved == "00000000-0000-0000-0000-000000000001"


def test_send_payload_rejects_wrong_sender_or_reply_domain():
    with pytest.raises(OutboundProviderError, match="sender domain"):
        build_resend_send(
            authorized_claim(), sender="Phil <phil@empire-ai.co.uk>",
            reply_to="reply@mail.empire-ai.co.uk",
        )
    with pytest.raises(OutboundProviderError, match="reply domain"):
        build_resend_send(
            authorized_claim(), sender="Phil <phil@mail.empire-ai.co.uk>",
            reply_to="reply@empire-ai.co.uk",
        )


def test_send_payload_accepts_multiline_equivalent_postal_footer():
    payload = build_resend_send(
        authorized_claim(
            body_text=(
                "Hello. Reply opt out.\n\n"
                "Empire-AI Intelligent Systems\n"
                "31 St Thomas St\nBolton\nBL1 2QR\nUK"
            )
        ),
        sender="Phil <phil@mail.empire-ai.co.uk>",
        reply_to="reply@mail.empire-ai.co.uk",
    )
    assert payload["to"] == ["buyer@example.com"]


def test_send_payload_requires_visible_opt_out_and_postal_footer():
    with pytest.raises(OutboundProviderError, match="opt-out"):
        build_resend_send(
            authorized_claim(body_text="Hello. 31 St Thomas St, Bolton, BL1 2QR, UK"),
            sender="Phil <phil@mail.empire-ai.co.uk>", reply_to="reply@mail.empire-ai.co.uk",
        )
    with pytest.raises(OutboundProviderError, match="postal footer"):
        build_resend_send(
            authorized_claim(body_text="Hello. Reply opt out."),
            sender="Phil <phil@mail.empire-ai.co.uk>", reply_to="reply@mail.empire-ai.co.uk",
        )
