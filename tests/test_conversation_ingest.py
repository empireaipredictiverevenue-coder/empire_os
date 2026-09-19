import pytest

from empire_os.conversation_ingest import normalise_provider_event


def vonage_payload():
    return {
        "conversation_uuid": "conv-v1",
        "event_uuid": "event-v1",
        "event_type": "speech_received",
        "timestamp": "2026-09-19T20:45:00+00:00",
        "direction": "inbound",
        "text": "I am interested",
        "actor": "buyer",
    }


def test_vonage_event_normalises_without_network():
    event = normalise_provider_event("vonage", vonage_payload())
    assert event.provider == "vonage"
    assert event.external_conversation_id == "conv-v1"
    assert len(event.payload_sha256) == 64
    canonical = event.to_conversation_event("conversation-1")
    assert canonical.direction.value == "inbound"
    assert canonical.text == "I am interested"
    assert canonical.evidence["provider"] == "vonage"
    assert canonical.evidence["payload_sha256"] == event.payload_sha256
    assert canonical.evidence["provider_schema"] == "v1"


def test_payload_hash_is_stable_across_mapping_order():
    first = vonage_payload()
    second = dict(reversed(list(first.items())))
    a = normalise_provider_event("vonage", first)
    b = normalise_provider_event("vonage", second)
    assert a.payload_sha256 == b.payload_sha256


def test_payload_hash_changes_when_provider_payload_changes():
    first = vonage_payload()
    second = dict(first)
    second["text"] = "Different text"
    a = normalise_provider_event("vonage", first)
    b = normalise_provider_event("vonage", second)
    assert a.payload_sha256 != b.payload_sha256


def test_elevenlabs_transcript_normalises_without_streaming():
    event = normalise_provider_event("elevenlabs", {
        "conversation_id": "el-1",
        "event_id": "el-event-1",
        "event_type": "transcript_segment",
        "occurred_at": "2026-09-19T20:46:00+00:00",
        "direction": "outbound",
        "transcript_text": "How can I help?",
    })
    assert event.text == "How can I help?"
    assert event.direction.value == "outbound"


def test_email_and_a2a_are_supported_channels():
    email = normalise_provider_event("email", {
        "thread_id": "thread-1",
        "message_id": "msg-1",
        "event_type": "reply_received",
        "occurred_at": "2026-09-19T20:47:00+00:00",
        "direction": "incoming",
        "body_text": "Send more info",
    })
    a2a = normalise_provider_event("a2a", {
        "context_id": "ctx-1",
        "message_id": "a2a-1",
        "event_type": "message_received",
        "occurred_at": "2026-09-19T20:48:00+00:00",
        "direction": "inbound",
        "text": "capabilities?",
    })
    assert email.direction.value == "inbound"
    assert a2a.external_conversation_id == "ctx-1"


def test_unknown_provider_fails_closed():
    with pytest.raises(ValueError, match="unsupported conversation provider"):
        normalise_provider_event("twilio", {})


def test_missing_provider_event_identity_fails_closed():
    with pytest.raises(ValueError, match="external_conversation_id required"):
        normalise_provider_event("email", {
            "message_id": "msg-1",
            "event_type": "reply_received",
            "occurred_at": "2026-09-19T20:47:00+00:00",
            "direction": "inbound",
        })


def test_occurred_at_requires_timezone():
    with pytest.raises(ValueError, match="include timezone"):
        normalise_provider_event("vonage", {
            **vonage_payload(),
            "timestamp": "2026-09-19T20:45:00",
        })


def test_occurred_at_requires_iso_timestamp():
    with pytest.raises(ValueError, match="ISO-8601"):
        normalise_provider_event("vonage", {
            **vonage_payload(),
            "timestamp": "not-a-time",
        })
