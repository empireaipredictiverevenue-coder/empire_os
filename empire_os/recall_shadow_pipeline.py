"""Verified Recall events -> private Digital Avatar shadow guidance."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from empire_os.digital_avatar import AvatarMeetingSession, DigitalAvatarIdentity
from empire_os.digital_avatar_meeting_memory import (
    AvatarMeetingMemory,
    build_avatar_meeting_memory,
)
from empire_os.digital_avatar_authority import (
    AvatarCloseProposal,
    AvatarCommercialAuthorityPolicy,
)
from empire_os.digital_avatar_response_task import (
    AvatarRealtimeResponseTask,
    build_realtime_response_task,
)
from empire_os.digital_avatar_shadow import AvatarShadowGuidance, build_shadow_guidance
from empire_os.meeting_gateway import (
    MeetingPlatform,
    MeetingSpeakerRole,
    ShadowMeetingState,
    build_shadow_meeting_state,
)
from empire_os.recall_meeting_adapter import normalize_verified_recall_event


@dataclass(frozen=True)
class RecallVerifiedEvent:
    payload: Mapping[str, Any]
    received_at: str
    verified: bool = False


@dataclass(frozen=True)
class RecallShadowPipelinePreview:
    meeting_state: ShadowMeetingState
    meeting_memory: AvatarMeetingMemory
    guidance: AvatarShadowGuidance
    response_task: AvatarRealtimeResponseTask
    event_count: int
    verified_event_count: int
    mode: str = "OBSERVE"
    read_only: bool = True
    persistence_performed: bool = False
    speech_execution: bool = False
    meeting_action_execution: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "meeting_state": self.meeting_state.as_dict(),
            "meeting_memory": self.meeting_memory.as_dict(),
            "guidance": self.guidance.as_dict(),
            "response_task": self.response_task.as_dict(),
        }


def build_recall_shadow_pipeline_preview(
    *,
    identity: DigitalAvatarIdentity,
    session: AvatarMeetingSession,
    platform: MeetingPlatform,
    events: Sequence[RecallVerifiedEvent],
    participant_roles: Mapping[str, MeetingSpeakerRole | str] | None = None,
    account_name: str,
    objective: str,

    proof_refs: Sequence[str] = (),
    commercial_terms_ref: str | None = None,
    predictive_inputs: Mapping[str, Any] | None = None,
    action_candidates: Sequence[Mapping[str, Any]] = (),
    commercial_policy: AvatarCommercialAuthorityPolicy | None = None,
    close_proposal: AvatarCloseProposal | None = None,
) -> RecallShadowPipelinePreview:
    identity.validate()
    session.validate()

    if not events:
        raise ValueError("at least one verified Recall event required")

    observations = []
    verified_count = 0
    for event in events:
        if event.verified is True:
            verified_count += 1
        observations.append(
            normalize_verified_recall_event(
                meeting_id=session.meeting_id,
                platform=platform,
                payload=event.payload,
                received_at=event.received_at,
                verified=event.verified,
                participant_roles=participant_roles or {},
            )
        )

    state = build_shadow_meeting_state(
        session=session,
        observations=observations,
    )
    memory = build_avatar_meeting_memory(
        session=session,
        observations=observations,
    )

    guidance = build_shadow_guidance(
        identity=identity,
        session=session,
        state=state,
        account_name=account_name,
        objective=objective,
        proof_refs=proof_refs,
        commercial_terms_ref=commercial_terms_ref,
        predictive_inputs=predictive_inputs,
        action_candidates=action_candidates,
        commercial_policy=commercial_policy,
        close_proposal=close_proposal,
    )
    response_task = build_realtime_response_task(
        memory=memory,
        strategy=guidance.strategy,
    )

    return RecallShadowPipelinePreview(
        meeting_state=state,
        meeting_memory=memory,
        guidance=guidance,
        response_task=response_task,
        event_count=len(events),
        verified_event_count=verified_count,
    )
