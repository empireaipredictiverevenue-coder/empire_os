from empire_os.digital_avatar_presence_token import AvatarPresenceClaims
from empire_os.digital_avatar_presence_transcript import (
    normalize_presence_transcript,
)


def claims():
    return AvatarPresenceClaims(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        bot_id="bot-123",
        issued_at=1790970000,
        expires_at=1790970300,
        nonce="nonce-1",
    )


def test_presence_transcript_is_fast_but_noncanonical():
    item = normalize_presence_transcript(
        claims=claims(),
        payload={
            "transcript": {
                "participant": {"id": 7, "name": "Buyer"},
                "words": [
                    {"text": "Can"},
                    {"text": "you"},
                    {"text": "deploy"},
                    {"text": "this?"},
                ],
            }
        },
        received_at="2026-10-02T20:00:00+00:00",
    )
    assert item.meeting_id == "meeting-001"
    assert item.avatar_id == "avatar-phil-v1"
    assert item.bot_id == "bot-123"
    assert item.participant_ref == "recall-participant:7"
    assert item.participant_name == "Buyer"
    assert item.text == "Can you deploy this?"
    assert item.truth_class == "SESSION_OBSERVED"
    assert item.canonical_evidence is False
    assert item.commercial_truth_allowed is False
    assert item.speech_execution_allowed is False
    assert item.execution_authority == "none"


def test_presence_transcript_accepts_bare_transcript_shape():
    item = normalize_presence_transcript(
        claims=claims(),
        payload={
            "participant": {"id": 9, "name": "CFO"},
            "words": [{"text": "What"}, {"text": "is"}, {"text": "price?"}],
            "is_final": False,
        },
        received_at="2026-10-02T20:00:01+00:00",
    )
    assert item.text == "What is price?"
    assert item.is_final is False


def test_presence_transcript_requires_words():
    import pytest

    with pytest.raises(ValueError, match="words list required"):
        normalize_presence_transcript(
            claims=claims(),
            payload={"transcript": {"participant": {"id": 7}}},
            received_at="2026-10-02T20:00:00+00:00",
        )
