from empire_os.digital_avatar import AvatarMeetingMode, AvatarMeetingSession
from empire_os.digital_avatar_meeting_memory import build_avatar_meeting_memory
from empire_os.meeting_gateway import (
    MeetingObservation,
    MeetingObservationKind,
    MeetingPlatform,
    MeetingSpeakerRole,
)


def session():
    return AvatarMeetingSession(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        provider="recall",
        mode=AvatarMeetingMode.SHADOW,
    )


def observation(event_id, text, role, evidence_ref, occurred_at):
    return MeetingObservation(
        meeting_id="meeting-001",
        external_meeting_id="bot-123",
        platform=MeetingPlatform.ZOOM,
        provider_event_id=event_id,
        kind=MeetingObservationKind.TRANSCRIPT_TURN,
        occurred_at=occurred_at,
        evidence_ref=evidence_ref,
        speaker_ref=f"speaker:{role.value}",
        speaker_role=role,
        text=text,
        is_final=True,
    )


def test_meeting_memory_preserves_exact_observed_turns_and_provenance():
    memory = build_avatar_meeting_memory(
        session=session(),
        observations=[
            observation(
                "event-1",
                "Can this integrate with our CRM?",
                MeetingSpeakerRole.BUYER,
                "evidence:1",
                "2026-10-02T18:00:00+00:00",
            ),
            observation(
                "event-2",
                "I will check the integration.",
                MeetingSpeakerRole.AVATAR_OWNER,
                "evidence:2",
                "2026-10-02T18:00:05+00:00",
            ),
        ],
    )
    assert len(memory.transcript_turns) == 2
    assert len(memory.buyer_turns) == 1
    assert memory.buyer_turns[0]["text"] == "Can this integrate with our CRM?"
    assert memory.evidence_refs == ("evidence:1", "evidence:2")
    assert memory.truth_class == "OBSERVED"
    assert memory.summary_generated is False
    assert memory.inference_performed is False


def test_meeting_memory_deduplicates_identical_provider_event():
    row = observation(
        "event-1",
        "We need a demo.",
        MeetingSpeakerRole.BUYER,
        "evidence:1",
        "2026-10-02T18:00:00+00:00",
    )
    memory = build_avatar_meeting_memory(
        session=session(),
        observations=[row, row],
    )
    assert len(memory.transcript_turns) == 1
    assert memory.evidence_refs == ("evidence:1",)


def test_latest_buyer_utterance_is_chronological():
    first = observation(
        "event-1",
        "What does it cost?",
        MeetingSpeakerRole.BUYER,
        "evidence:1",
        "2026-10-02T18:00:00+00:00",
    )
    second = observation(
        "event-2",
        "Can we start next week?",
        MeetingSpeakerRole.BUYER,
        "evidence:2",
        "2026-10-02T18:01:00+00:00",
    )
    memory = build_avatar_meeting_memory(
        session=session(),
        observations=[second, first],
    )
    assert memory.latest_buyer_utterance["text"] == "Can we start next week?"
