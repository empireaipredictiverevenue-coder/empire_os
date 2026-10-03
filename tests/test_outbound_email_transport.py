import json
from uuid import uuid4

import pytest

from empire_os.outbound_email_transport import PostalEmailTransport
from empire_os.outbound_governor_executor import (
    OutboundGovernorExecutionError,
    execute_governor_decision,
)
from empire_os.outbound_provider import OutboundProviderError


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode()

    def close(self):
        pass


def test_postal_transport_maps_validated_payload_and_returns_message_id():
    seen = {}

    def opener(req, timeout):
        seen["url"] = req.full_url
        seen["headers"] = {k.lower(): v for k, v in req.header_items()}
        seen["payload"] = json.loads(req.data.decode())
        seen["timeout"] = timeout
        return FakeResponse({
            "status": "success",
            "data": {"message_id": "postal-message@example.test"},
        })

    transport = PostalEmailTransport(
        base_url="https://postal.example.test",
        api_key="secret-key",
        opener=opener,
    )
    message_id = transport.send({
        "from": "Empire AI <outreach@empire-ai.co.uk>",
        "to": ["buyer@example.com"],
        "reply_to": ["reply+abc@mail.empire-ai.co.uk"],
        "subject": "Hello",
        "text": "Body",
        "html": "<p>Body</p>",
        "headers": {"List-Unsubscribe": "<mailto:reply@mail.empire-ai.co.uk>"},
        "tags": [{"name": "intent_id", "value": "abc"}],
        "_sender_address": "outreach@empire-ai.co.uk",
        "_idempotency_key": "outbound/abc",
    })

    assert message_id == "postal-message@example.test"
    assert seen["url"].endswith("/api/v1/send/message")
    assert seen["headers"]["x-server-api-key"] == "secret-key"
    assert seen["payload"]["to"] == ["buyer@example.com"]
    assert seen["payload"]["reply_to"] == "reply+abc@mail.empire-ai.co.uk"
    assert seen["payload"]["plain_body"] == "Body"
    assert seen["payload"]["html_body"] == "<p>Body</p>"
    assert seen["payload"]["tag"] == "abc"
    assert seen["payload"]["headers"]["X-Empire-Idempotency-Key"] == "outbound/abc"


def test_postal_transport_rejects_unvalidated_payload():
    with pytest.raises(OutboundProviderError, match="validated outbound payload"):
        PostalEmailTransport(
            base_url="https://postal.example.test",
            api_key="secret-key",
        ).send({"to": ["buyer@example.com"]})


def test_governor_accepts_injected_transport_without_resend_configuration():
    intent_id = str(uuid4())
    calls = []

    class FakePostal:
        provider = "postal"

        def send(self, payload):
            assert payload["_idempotency_key"] == f"outbound/{intent_id}"
            return "postal-provider-message-id"

    def sender_rpc(name, payload):
        calls.append((name, payload))
        if name == "claim_outbound_send":
            return {
                "decision": "authorized_send",
                "actual_revenue": False,
                "channel": "email",
                "intent_id": intent_id,
                "recipient": "buyer@example.com",
                "subject": "Empire AI",
                "body_text": (
                    "A governed message. To unsubscribe, reply opt out.\n\n"
                    "31 St Thomas St, Bolton, BL1 2QR, UK"
                ),
            }
        if name == "record_outbound_delivery":
            return {"ok": True}
        raise AssertionError(name)

    result = execute_governor_decision(
        {
            "decision": "AUTO_SEND_ELIGIBLE",
            "intent_id": intent_id,
            "mode": "GUARDED_EXECUTE",
            "mutation_authorized": True,
        },
        sender_rpc=sender_rpc,
        actor="test-governor",
        sender="outreach@empire-ai.co.uk",
        reply_to="reply@mail.empire-ai.co.uk",
        email_transport=FakePostal(),
    )

    assert result["decision"] == "AUTO_SENT"
    assert calls[-1][0] == "record_outbound_delivery"
    assert calls[-1][1]["p_payload"] == {
        "provider": "postal",
        "governor": True,
    }



def test_governor_marks_unknown_provider_outcome_for_reconciliation():
    intent_id = str(uuid4())
    calls = []

    class FailingPostal:
        provider = "postal"

        def send(self, payload):
            raise OutboundProviderError("Postal send failed: timeout")

    def sender_rpc(name, payload):
        calls.append((name, payload))

        if name == "claim_outbound_send":
            return {
                "decision": "authorized_send",
                "actual_revenue": False,
                "channel": "email",
                "intent_id": intent_id,
                "recipient": "buyer@example.com",
                "subject": "Empire AI",
                "body_text": (
                    "Governed message. To unsubscribe, reply opt out.\n\n"
                    "31 St Thomas St, Bolton, BL1 2QR, UK"
                ),
            }

        if name == "record_outbound_delivery":
            return {"ok": True}

        raise AssertionError(name)

    with pytest.raises(
        OutboundGovernorExecutionError,
        match="reconciliation required",
    ):
        execute_governor_decision(
            {
                "decision": "AUTO_SEND_ELIGIBLE",
                "intent_id": intent_id,
                "mode": "GUARDED_EXECUTE",
                "mutation_authorized": True,
            },
            sender_rpc=sender_rpc,
            actor="test-governor",
            sender="outreach@empire-ai.co.uk",
            reply_to="reply@mail.empire-ai.co.uk",
            email_transport=FailingPostal(),
        )

    assert calls[-1][0] == "record_outbound_delivery"
    assert calls[-1][1]["p_event_type"] == "reconciliation_required"
    assert calls[-1][1]["p_provider_message_id"] == ""
    assert calls[-1][1]["p_payload"]["provider"] == "postal"
    assert calls[-1][1]["p_payload"]["provider_outcome"] == "unknown"
