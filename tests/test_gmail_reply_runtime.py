from empire_os.gmail_reply_runtime import (
    list_canonical_gmail_intents,
    process_gmail_message,
)

INTENT_ID = "00000000-0000-0000-0000-000000000001"
THREAD_ID = "thread/with+chars"


class FakeRequest:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def __call__(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if method == "GET":
            return self.rows
        raise AssertionError((method, path, payload))


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
            }
        raise AssertionError(name)


def intent():
    return {
        "id": INTENT_ID,
        "channel": "email",
        "recipient": "buyer@example.com",
        "normalized_recipient": "buyer@example.com",
        "status": "sent",
        "metadata": {
            "provider": "gmail",
            "gmail_thread_id": THREAD_ID,
        },
    }


def message():
    return {
        "id": "gmail-reply-1",
        "thread_id": THREAD_ID,
        "from": "Buyer <buyer@example.com>",
        "subject": "Re: pilot",
        "body": "Interested. Tell me more.",
        "labels": ["INBOX"],
        "email_ts": "2026-09-25T09:00:00+00:00",
    }


def test_lookup_is_narrow_sent_gmail_thread_projection():
    request = FakeRequest([intent()])
    rows = list_canonical_gmail_intents(
        THREAD_ID,
        request_factory=request,
    )
    assert rows == [intent()]
    method, path, payload = request.calls[0]
    assert method == "GET"
    assert payload is None
    assert "channel=eq.email" in path
    assert "status=eq.sent" in path
    assert "metadata->>provider=eq.gmail" in path
    assert "thread%2Fwith%2Bchars" in path
    assert "limit=2" in path


def test_process_uses_canonical_lookup_then_reply_ingest_only():
    request = FakeRequest([intent()])
    rpc = FakeRpc()
    result = process_gmail_message(
        message(),
        self_addresses=["founder@example.com"],
        request_factory=request,
        reply_rpc=rpc,
    )
    assert result["ignored"] is False
    assert result["classification"] == "positive"
    assert result["outbound_sent"] is False
    assert result["actual_revenue"] is False
    assert [name for name, _ in rpc.calls] == [
        "ingest_outbound_reply",
        "classify_outbound_reply",
    ]


def test_missing_thread_never_touches_database():
    request = FakeRequest([intent()])
    rpc = FakeRpc()
    candidate = message()
    candidate["thread_id"] = ""
    result = process_gmail_message(
        candidate,
        request_factory=request,
        reply_rpc=rpc,
    )
    assert result["ignored"] is True
    assert result["reason"] == "missing_thread_id"
    assert request.calls == []
    assert rpc.calls == []


def test_no_canonical_match_is_inert():
    request = FakeRequest([])
    rpc = FakeRpc()
    result = process_gmail_message(
        message(),
        request_factory=request,
        reply_rpc=rpc,
    )
    assert result["ignored"] is True
    assert result["reason"] == "no_canonical_thread_match"
    assert rpc.calls == []
