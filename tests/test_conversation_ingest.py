import pytest

from empire_os.conversation_ingest import normalise_provider_event


def test_vonage_event_normalises_without_network():
    event = normalise_provider_event("vonage", {
        "conversation_uuid": "conv-v1",
        "event_uuid": "event-v1",
        "event_type": "speech_received",
        "timestamp": "2026-09-19T22:45:00+00:00",
        "direction": "inbound",
        "text": "I am interested",
        "actor": "buyer",
    })
    assert event.provider == "vonage"
    assert event.external_conversation_id == "conv-v1"
    canonical = event.to_conversation_event("conversation-1")
    assert canonical.direction.value == "inbound"
    assert canonical.text == "I am interested"
    assert canonical.evidence["provider"] == "vonage"


def test_elevenlabs_transcript_normalises_without_streaming():
    event = normalise_provider_event("elevenlabs", {
        "conversation_id": "el-1",
        "event_id": "el-event-1",
        "event_type": "transcript_segment",
        "occurred_at": "2026-09-19T22:46:00+00:00",
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
        "occurred_at": "2026-09-19T22:47:00+00:00",
        "direction": "incoming",
        "body_text": "Send more info",
    })
    a2a = normalise_provider_event("a2a", {
        "context_id": "ctx-1",
        "message_id": "a2a-1",
        "event_type": "message_received",
        "occurred_at": "2026-09-19T22:48:00+00:00",
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
            "occurred_at": "2026-09-19T22:47:00+00:00",
            "direction": "inbound",
        })
