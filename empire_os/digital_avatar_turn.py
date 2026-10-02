"""Grounded, non-speaking Copilot turn approval for Digital Avatar."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping

from empire_os.digital_avatar import AvatarMeetingSession
from empire_os.digital_avatar_authority import AvatarCommercialAuthorityDecision


class AvatarTurnPurpose(str, Enum):
    ANSWER = "answer"
    QUESTION = "question"
    CLARIFY = "clarify"
    HANDLE_OBJECTION = "handle_objection"
    COMMERCIAL_CLOSE = "commercial_close"


class AvatarClaimTruth(str, Enum):
    OBSERVED = "OBSERVED"
    VERIFIED = "VERIFIED"
    INFERRED = "INFERRED"
    FORECAST = "FORECAST"


@dataclass(frozen=True)
class AvatarTurnClaim:
    text: str
    truth_class: AvatarClaimTruth
    evidence_refs: tuple[str, ...] = ()

    def validate_structure(self) -> None:
        if not self.text.strip():
            raise ValueError("turn claim text required")


@dataclass(frozen=True)
class AvatarTurnDraft:
    meeting_id: str
    avatar_id: str
    purpose: AvatarTurnPurpose
    text: str
    claims: tuple[AvatarTurnClaim, ...] = ()
    strategy_evidence_refs: tuple[str, ...] = ()

    def validate_structure(self) -> None:
        if not self.meeting_id.strip() or not self.avatar_id.strip():
            raise ValueError("meeting_id and avatar_id required")
        if not self.text.strip():
            raise ValueError("turn draft text required")
        for claim in self.claims:
            claim.validate_structure()


@dataclass(frozen=True)
class AvatarTurnApprovalDecision:
    ready_for_human_approval: bool
    requires_explicit_human_approval: bool
    human_takeover_required: bool
    unsupported_claim_count: int
    blockers: tuple[str, ...]
    speech_execution_allowed: bool = False
    chat_execution_allowed: bool = False
    execution_authority: str = "none"
    side_effects: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_avatar_turn_for_approval(
    *,
    session: AvatarMeetingSession,
    draft: AvatarTurnDraft,
    commercial_authority: AvatarCommercialAuthorityDecision | Mapping[str, Any] | None = None,
) -> AvatarTurnApprovalDecision:
    session.validate()
    draft.validate_structure()

    blockers: list[str] = []
    unsupported_claims = 0

    if draft.meeting_id != session.meeting_id:
        blockers.append("turn_meeting_identity_mismatch")
    if draft.avatar_id != session.avatar_id:
        blockers.append("turn_avatar_identity_mismatch")

    for claim in draft.claims:
        if not claim.evidence_refs:
            unsupported_claims += 1
    if unsupported_claims:
        blockers.append("material_claim_evidence_missing")

    if not draft.strategy_evidence_refs:
        blockers.append("strategy_evidence_missing")

    human_takeover_required = False


    if draft.purpose == AvatarTurnPurpose.COMMERCIAL_CLOSE:
        if commercial_authority is None:
            blockers.append("commercial_authority_decision_missing")
            human_takeover_required = True
        else:
            if isinstance(commercial_authority, AvatarCommercialAuthorityDecision):
                policy_eligible = commercial_authority.policy_eligible
                takeover = commercial_authority.human_takeover_required
            else:
                policy_eligible = commercial_authority.get("policy_eligible") is True
                takeover = commercial_authority.get("human_takeover_required") is True
            if not policy_eligible:
                blockers.append("commercial_close_outside_delegated_policy")
            if takeover:
                blockers.append("commercial_human_takeover_required")
                human_takeover_required = True

    ready = not blockers
    return AvatarTurnApprovalDecision(
        ready_for_human_approval=ready,
        requires_explicit_human_approval=True,
        human_takeover_required=human_takeover_required,
        unsupported_claim_count=unsupported_claims,
        blockers=tuple(sorted(set(blockers))),
    )
