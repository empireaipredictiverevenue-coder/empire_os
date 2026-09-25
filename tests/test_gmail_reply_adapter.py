from empire_os.gmail_reply_adapter import (
    correlate_gmail_reply,
    ingest_gmail_reply,
    visible_reply_text,
)

INTENT_ID = "00000000-0000-0000-0000-000000000001"
THREAD_ID = "gmail-thread-1"


def intent(**overrides):
    row = {
        "id": INTENT_ID,
        "channel": "email",
        "recipient": "Buyer <buyer@example.com>",
        "normalized_recipient": "buyer@example.com",
        "status": "sent",
        "metadata": {
            "provider": "gmail",
            "provider_message_id": "gmail-sent-1",
            "gmail_thread_id": THREAD_ID,
        },
    }
    row.update(overrides)
    return row


def message(**overrides):
    row = {
        "id": "gmail-reply-1",
        "thread_id": THREAD_ID,
        "from": "Buyer <buyer@example.com>",
        "to": ["founder@example.com"],
        "subject": "Re: pilot",
        "body": "Interested. Tell me more.",
        "labels": ["INBOX", "UNREAD"],
        "email_ts": "2026-09-25T08:30:00+00:00",
    }
    row.update(overrides)
    return row


class FakeRpc:
    def __init__(self):
        self.calls = []

    def __call__(self, name, params):
        self.calls.append((name, params))
        if name == "ingest_outbound_reply":
            return {
                "decision": "recorded",
                "reply_id": "00000000-0000-0000-0000-000000000099",
            }
        if name == "classify_outbound_reply":
            return {
                "decision": "classified",
                "classification": params["p_classification"],
                "suppressed": False,
            }
        raise AssertionError(name)


def test_exact_thread_and_sender_match_ingests_untrusted_reply():
    rpc = FakeRpc()
    result = ingest_gmail_reply(
        message(),
        [intent()],
        rpc,
        self_addresses=["founder@example.com"],
    )

    assert result["ignored"] is False
    assert result["intent_id"] == INTENT_ID
    assert result["classification"] == "positive"
    assert result["classification_auto_applied"] is True
    assert result["outbound_sent"] is False
    assert result["actual_revenue"] is False

    ingest_name, ingest_params = rpc.calls[0]
    assert ingest_name == "ingest_outbound_reply"
    assert ingest_params["p_intent_id"] == INTENT_ID
    assert ingest_params["p_provider_message_id"] == "gmail-reply-1"
    assert ingest_params["p_metadata"]["provider"] == "gmail"
    assert ingest_params["p_metadata"]["untrusted_content"] is True
    assert ingest_params["p_metadata"]["gmail_thread_id"] == THREAD_ID
    assert rpc.calls[1][0] == "classify_outbound_reply"


def test_thread_match_without_sender_match_is_rejected():
    result = correlate_gmail_reply(
        message(from_="ignored"),
        [intent()],
    )
    assert result["matched"] is True

    wrong = message()
    wrong["from"] = "Other <other@example.com>"
    result = correlate_gmail_reply(wrong, [intent()])
    assert result == {
        "matched": False,
        "reason": "no_canonical_thread_match",
    }


def test_self_sent_draft_and_delivery_status_messages_are_ignored():
    self_result = correlate_gmail_reply(
        message(from_="ignored"),
        [intent()],
        self_addresses=["buyer@example.com"],
    )
    assert self_result["matched"] is False
    assert self_result["reason"] == "self_message"

    sent = message(labels=["SENT"])
    result = correlate_gmail_reply(sent, [intent()])
    assert result["reason"] == "outbound_or_draft_message"

    draft = message(labels=["DRAFT"])
    result = correlate_gmail_reply(draft, [intent()])
    assert result["reason"] == "outbound_or_draft_message"

    dsn = message()
    dsn["from"] = "Mail Delivery Subsystem <mailer-daemon@googlemail.com>"
    result = correlate_gmail_reply(dsn, [intent()])
    assert result["reason"] == "delivery_status_message"


def test_requires_exactly_one_canonical_sent_gmail_intent():
    assert correlate_gmail_reply(message(), [])["reason"] == (
        "no_canonical_thread_match"
    )

    pending = intent(status="pending_approval")
    assert correlate_gmail_reply(message(), [pending])["reason"] == (
        "no_canonical_thread_match"
    )

    resend = intent(metadata={"provider": "resend", "gmail_thread_id": THREAD_ID})
    assert correlate_gmail_reply(message(), [resend])["reason"] == (
        "no_canonical_thread_match"
    )

    duplicate = dict(intent())
    duplicate["id"] = "00000000-0000-0000-0000-000000000002"
    assert correlate_gmail_reply(
        message(),
        [intent(), duplicate],
    )["reason"] == "ambiguous_canonical_thread_match"


def test_quoted_history_is_not_used_for_classification():
    body = (
        "No thanks.\n\n"
        "On Thu, Sep 24, 2026 at 10:00 AM Phil wrote:\n"
        "> Interested buyers can reply here.\n"
    )
    assert visible_reply_text(body) == "No thanks."

    rpc = FakeRpc()
    result = ingest_gmail_reply(
        message(body=body),
        [intent()],
        rpc,
    )
    assert result["classification"] == "negative"
    assert rpc.calls[1][1]["p_classification"] == "negative"


def test_unclassified_reply_is_recorded_but_not_auto_applied():
    rpc = FakeRpc()
    result = ingest_gmail_reply(
        message(body="Thanks for the note."),
        [intent()],
        rpc,
    )
    assert result["classification"] == "other"
    assert result["classification_auto_applied"] is False
    assert [name for name, _ in rpc.calls] == ["ingest_outbound_reply"]
