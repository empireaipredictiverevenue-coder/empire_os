"""Evidence-preserving meeting memory for Empire Digital Avatar."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from empire_os.meeting_gateway import (
    MeetingObservation,
    MeetingObservationKind,
    MeetingSpeakerRole,
    build_shadow_meeting_state,
)
from empire_os.digital_avatar import AvatarMeetingSession


@dataclass(frozen=True)
class AvatarMeetingMemory:
    meeting_id: str
    avatar_id: str
    participant_refs: tuple[str, ...]
    transcript_turns: tuple[dict[str, Any], ...]
    buyer_turns: tuple[dict[str, Any], ...]
    evidence_refs: tuple[str, ...]
    latest_buyer_utterance: dict[str, Any] | None
    mode: str = "OBSERVE"
    truth_class: str = "OBSERVED"
    summary_generated: bool = False
    inference_performed: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_avatar_meeting_memory(
    *,
    session: AvatarMeetingSession,
    observations: Iterable[MeetingObservation],
) -> AvatarMeetingMemory:
    state = build_shadow_meeting_state(
        session=session,
        observations=observations,
    )

    turns = tuple(
        row
        for row in state.observations
        if row.get("kind") == MeetingObservationKind.TRANSCRIPT_TURN.value
        and row.get("is_final") is True
    )
    buyer_turns = tuple(
        row
        for row in turns
        if row.get("speaker_role") == MeetingSpeakerRole.BUYER.value
    )
    participant_refs = tuple(
        dict.fromkeys(
            str(row.get("speaker_ref") or "").strip()
            for row in turns
            if str(row.get("speaker_ref") or "").strip()
        )
    )
    evidence_refs = tuple(
        dict.fromkeys(
            str(row.get("evidence_ref") or "").strip()
            for row in state.observations
            if str(row.get("evidence_ref") or "").strip()
        )
    )

    return AvatarMeetingMemory(
        meeting_id=session.meeting_id,
        avatar_id=session.avatar_id,
        participant_refs=participant_refs,
        transcript_turns=turns,
        buyer_turns=buyer_turns,
        evidence_refs=evidence_refs,
        latest_buyer_utterance=(
            dict(state.latest_buyer_utterance)
            if state.latest_buyer_utterance is not None
            else None
        ),
    )
