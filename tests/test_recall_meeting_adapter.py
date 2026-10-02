import pytest

from empire_os.meeting_gateway import MeetingPlatform, MeetingSpeakerRole
from empire_os.recall_meeting_adapter import normalize_verified_recall_event


def transcript_payload():
    return {
        "event": "transcript.data",
        "data": {
            "bot": {"id": "bot-123"},
            "transcript": {"id": "transcript-456"},
            "data": {
                "participant": {"id": 7, "name": "Buyer"},
                "words": [{"text": "We"}, {"text": "need"}, {"text": "this"}],
            },
        },
    }


def test_verified_transcript_normalizes_to_meeting_observation():
    observation = normalize_verified_recall_event(
        meeting_id="meeting-001",
        platform=MeetingPlatform.ZOOM,
        payload=transcript_payload(),
        received_at="2026-10-02T18:00:00+00:00",
        verified=True,
        participant_roles={"7": MeetingSpeakerRole.BUYER},
    )
    assert observation.meeting_id == "meeting-001"
    assert observation.external_meeting_id == "bot-123"
    assert observation.text == "We need this"
    assert observation.speaker_role == MeetingSpeakerRole.BUYER
    assert observation.is_final is True
    assert observation.evidence_ref.startswith("recall:bot-123:transcript-456:")


def test_unverified_recall_event_is_rejected():
    with pytest.raises(ValueError, match="unverified Recall event rejected"):
        normalize_verified_recall_event(
            meeting_id="meeting-001",
            platform=MeetingPlatform.ZOOM,
            payload=transcript_payload(),
            received_at="2026-10-02T18:00:00+00:00",
            verified=False,
        )


def test_same_payload_produces_stable_provider_event_id():
    kwargs = {
        "meeting_id": "meeting-001",
        "platform": MeetingPlatform.ZOOM,
        "payload": transcript_payload(),
        "received_at": "2026-10-02T18:00:00+00:00",
        "verified": True,
        "participant_roles": {"7": "buyer"},
    }
    first = normalize_verified_recall_event(**kwargs)
    second = normalize_verified_recall_event(**kwargs)
    assert first.provider_event_id == second.provider_event_id
    assert first.fingerprint() == second.fingerprint()


def test_unsupported_event_is_rejected():
    payload = transcript_payload()
    payload["event"] = "unknown.event"
    with pytest.raises(ValueError, match="unsupported Recall real-time event"):
        normalize_verified_recall_event(
            meeting_id="meeting-001",
            platform=MeetingPlatform.ZOOM,
            payload=payload,
            received_at="2026-10-02T18:00:00+00:00",
            verified=True,
        )


def test_invalid_explicit_participant_role_is_rejected():
    with pytest.raises(ValueError, match="invalid explicit participant role"):
        normalize_verified_recall_event(
            meeting_id="meeting-001",
            platform=MeetingPlatform.ZOOM,
            payload=transcript_payload(),
            received_at="2026-10-02T18:00:00+00:00",
            verified=True,
            participant_roles={"7": "decision_maker"},
        )
