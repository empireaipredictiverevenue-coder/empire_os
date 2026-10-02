"""Human-gated Copilot handoff packets for Empire Digital Avatar."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from empire_os.digital_avatar import (
    AvatarMeetingMode,
    AvatarMeetingSession,
    DigitalAvatarIdentity,
)
from empire_os.digital_avatar_turn import (
    AvatarTurnApprovalDecision,
    AvatarTurnDraft,
    assess_avatar_turn_for_approval,
)


@dataclass(frozen=True)
class AvatarCopilotHandoff:
    meeting_id: str
    avatar_id: str
    owner_name: str
    draft_text: str
    purpose: str
    decision: AvatarTurnApprovalDecision
    evidence_refs: tuple[str, ...]
    ready_for_human_approval: bool
    human_approval_required: bool = True
    human_approval_recorded: bool = False
    transmission_performed: bool = False
    speech_execution_allowed: bool = False
    chat_execution_allowed: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["decision"] = self.decision.as_dict()
        return data


def _evidence_refs(draft: AvatarTurnDraft) -> tuple[str, ...]:
    values = list(draft.strategy_evidence_refs)
    for claim in draft.claims:
        values.extend(claim.evidence_refs)
    return tuple(
        dict.fromkeys(
            str(value or "").strip()
            for value in values
            if str(value or "").strip()
        )
    )


def build_avatar_copilot_handoff(
    *,
    identity: DigitalAvatarIdentity,
    session: AvatarMeetingSession,
    draft: AvatarTurnDraft,
    commercial_authority: Mapping[str, Any] | None = None,
) -> AvatarCopilotHandoff:
    identity.validate()
    session.validate()
    draft.validate_structure()

    if session.mode != AvatarMeetingMode.COPILOT:
        raise ValueError("copilot handoff requires COPILOT mode")
    if session.avatar_id != identity.avatar_id:
        raise ValueError("copilot handoff avatar identity mismatch")
    if draft.meeting_id != session.meeting_id:
        raise ValueError("copilot handoff meeting identity mismatch")
    if draft.avatar_id != identity.avatar_id:
        raise ValueError("copilot handoff draft avatar mismatch")

    decision = assess_avatar_turn_for_approval(
        session=session,
        draft=draft,
        commercial_authority=commercial_authority,
    )


    return AvatarCopilotHandoff(
        meeting_id=session.meeting_id,
        avatar_id=identity.avatar_id,
        owner_name=identity.owner_name,
        draft_text=draft.text,
        purpose=draft.purpose.value,
        decision=decision,
        evidence_refs=_evidence_refs(draft),
        ready_for_human_approval=decision.ready_for_human_approval,
    )
