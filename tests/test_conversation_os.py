import pytest

from empire_os.conversation_os import (
    ConversationChannel,
    ConversationDirection,
    ConversationEventRecord,
    normalise_conversation_row,
)


def test_normalise_conversation_preserves_canonical_links():
    record = normalise_conversation_row({
        "id": "conversation-1",
        "channel": "email",
        "state": "engaged",
        "prospect_id": "prospect-1",
        "entity_id": "entity-1",
        "external_conversation_id": "provider-thread-1",
    })
    assert record.channel is ConversationChannel.EMAIL
    assert record.state == "engaged"
    assert record.prospect_id == "prospect-1"
    assert record.external_conversation_id == "provider-thread-1"


def test_conversation_without_canonical_participant_fails_closed():
    with pytest.raises(ValueError, match="canonical participant"):
        normalise_conversation_row({
            "id": "conversation-1",
            "channel": "voice",
            "state": "open",
        })
def test_invalid_channel_is_rejected():
    with pytest.raises(ValueError):
        normalise_conversation_row({
            "id": "conversation-1",
            "channel": "carrier_pigeon",
            "state": "open",
            "buyer_id": "buyer-1",
        })


def test_event_record_is_explicit_about_direction_and_evidence():
    event = ConversationEventRecord(
        conversation_id="conversation-1",
        event_type="reply_received",
        direction=ConversationDirection.INBOUND,
        occurred_at="2026-09-19T17:00:00+00:00",
        actor="buyer",
        text="Interested",
        evidence={"source": "provider_webhook"},
    )
    payload = event.as_dict()
    assert payload["direction"] == "inbound"
    assert payload["evidence"] == {"source": "provider_webhook"}
