import base64
from email import message_from_bytes

import pytest

from empire_os.gmail_api_transport import (
    build_gmail_message,
    send_with_gmail_api,
)
from empire_os.outbound_provider import OutboundProviderError


POSTAL = "68 Wentbridge Road, Bolton, BL1 2QR, UK"


def claim():
    return {
        "decision": "authorized_send",
        "actual_revenue": False,
        "channel": "email",
        "intent_id": "11111111-1111-4111-8111-111111111111",
        "recipient": "seed@example.com",
        "subject": "Empire seed test",
        "body_text": (
            "Controlled seed test only.\n\n"
            "Opt out at any time.\n"
            + POSTAL
        ),
    }


def test_requires_database_authorized_claim():
    row = claim()
    row["decision"] = "observe_only"

    with pytest.raises(
        OutboundProviderError,
        match="database-authorized",
    ):
        build_gmail_message(
            row,
            sender="Founder <founder@empire-ai.co.uk>",
            reply_to="reply@mail.empire-ai.co.uk",
        )


def test_builds_governed_reply_alias():
    message = build_gmail_message(
        claim(),
        sender="Founder <founder@empire-ai.co.uk>",
        reply_to="reply@mail.empire-ai.co.uk",
    )

    assert message["To"] == "seed@example.com"
    assert (
        message["Reply-To"]
        == "reply+11111111-1111-4111-8111-111111111111"
        "@mail.empire-ai.co.uk"
    )
    assert "List-Unsubscribe" in message
    assert (
        message["X-Empire-Intent-ID"]
        == "11111111-1111-4111-8111-111111111111"
    )


class Execute:
    def __init__(self, parent):
        self.parent = parent

    def execute(self):
        return {
            "id": "gmail-message-1",
            "threadId": "gmail-thread-1",
        }


class Messages:
    def __init__(self, parent):
        self.parent = parent

    def send(self, *, userId, body):
        self.parent.user_id = userId
        self.parent.body = body
        return Execute(self.parent)


class Users:
    def __init__(self, parent):
        self.parent = parent

    def messages(self):
        return Messages(self.parent)


class FakeService:
    def users(self):
        return Users(self)


def test_send_uses_gmail_api_raw_message():
    service = FakeService()

    result = send_with_gmail_api(
        claim(),
        sender="Founder <founder@empire-ai.co.uk>",
        reply_to="reply@mail.empire-ai.co.uk",
        service=service,
    )

    assert result["provider"] == "gmail"
    assert result["provider_message_id"] == "gmail-message-1"
    assert service.user_id == "me"

    raw = base64.urlsafe_b64decode(
        service.body["raw"].encode("ascii")
    )
    message = message_from_bytes(raw)

    assert message["To"] == "seed@example.com"
    assert message["Subject"] == "Empire seed test"
