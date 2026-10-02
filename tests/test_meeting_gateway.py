import pytest

from empire_os.digital_avatar import AvatarMeetingMode, AvatarMeetingSession
from empire_os.meeting_gateway import (
    MeetingObservation,
    MeetingObservationKind,
    MeetingPlatform,
    MeetingSpeakerRole,
    build_shadow_meeting_state,
)


def session():
    return AvatarMeetingSession(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        provider="meeting-gateway",
        mode=AvatarMeetingMode.SHADOW,
    )


def buyer_turn(event_id="evt-1", text="We need this live before Q4"):
    return MeetingObservation(
        meeting_id="meeting-001",
        external_meeting_id="zoom-abc",
        platform=MeetingPlatform.ZOOM,
        provider_event_id=event_id,
        kind=MeetingObservationKind.TRANSCRIPT_TURN,
        occurred_at="2026-10-02T16:00:00+00:00",
        evidence_ref=f"provider:zoom:{event_id}",
        speaker_ref="buyer-1",
        speaker_name="Buyer",
        speaker_role=MeetingSpeakerRole.BUYER,
        text=text,
        is_final=True,
    )


def test_shadow_state_preserves_observed_buyer_utterance():
    state = build_shadow_meeting_state(
        session=session(),
        observations=[buyer_turn()],
    )
    assert state.observation_count == 1
    assert state.transcript_turn_count == 1
    assert state.latest_buyer_utterance["text"] == "We need this live before Q4"
    assert state.latest_buyer_utterance["evidence_ref"] == "provider:zoom:evt-1"
    assert state.private_guidance_only is True
    assert state.speech_execution is False
    assert state.execution_authority == "none"


def test_exact_duplicate_provider_event_is_idempotent():
    turn = buyer_turn()
    state = build_shadow_meeting_state(
        session=session(),
        observations=[turn, turn],
    )
    assert state.observation_count == 1


def test_conflicting_duplicate_provider_event_fails_closed():
    with pytest.raises(ValueError, match="conflicting provider_event_id reuse"):
        build_shadow_meeting_state(
            session=session(),
            observations=[
                buyer_turn(text="first"),
                buyer_turn(text="different"),
            ],
        )


def test_partial_transcript_is_not_promoted_to_final_buyer_utterance():
    partial = MeetingObservation(
        meeting_id="meeting-001",
        external_meeting_id="meet-abc",
        platform=MeetingPlatform.GOOGLE_MEET,
        provider_event_id="evt-partial",
        kind=MeetingObservationKind.TRANSCRIPT_TURN,
        occurred_at="2026-10-02T16:00:00+00:00",
        evidence_ref="provider:meet:evt-partial",
        speaker_ref="buyer-1",
        speaker_role=MeetingSpeakerRole.BUYER,
        text="we might",
        is_final=False,
    )
    state = build_shadow_meeting_state(
        session=session(),
        observations=[partial],
    )
    assert state.transcript_turn_count == 0
    assert state.latest_buyer_utterance is None


def test_shadow_state_rejects_non_shadow_session():
    non_shadow = AvatarMeetingSession(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        provider="meeting-gateway",
        mode=AvatarMeetingMode.COPILOT,
    )
    with pytest.raises(ValueError, match="requires SHADOW mode"):
        build_shadow_meeting_state(
            session=non_shadow,
            observations=[buyer_turn()],
        )
