"""Fail-closed mode-transition policy for Empire Digital Avatar."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.digital_avatar import AvatarMeetingMode, AvatarMeetingSession


_MODE_ORDER = (
    AvatarMeetingMode.SHADOW,
    AvatarMeetingMode.COPILOT,
    AvatarMeetingMode.REPRESENT,
    AvatarMeetingMode.NEGOTIATE,
    AvatarMeetingMode.CLOSE,
)


@dataclass(frozen=True)
class AvatarModeTransitionEvidence:
    owner_approval_evidence_ref: str | None = None
    delegated_authority_evidence_ref: str | None = None
    commercial_terms_evidence_ref: str | None = None


@dataclass(frozen=True)
class AvatarModeTransitionDecision:
    meeting_id: str
    current_mode: AvatarMeetingMode
    target_mode: AvatarMeetingMode
    policy_eligible: bool
    execution_allowed: bool
    blockers: tuple[str, ...]
    emergency_shadow_available: bool = True
    execution_authority: str = "none"
    side_effects: bool = False

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["current_mode"] = self.current_mode.value
        data["target_mode"] = self.target_mode.value
        return data


def assess_avatar_mode_transition(
    *,
    session: AvatarMeetingSession,
    target_mode: AvatarMeetingMode,
    evidence: AvatarModeTransitionEvidence | None = None,
    runtime_authority: str = "observe",
) -> AvatarModeTransitionDecision:
    session.validate()
    evidence = evidence or AvatarModeTransitionEvidence()

    if runtime_authority.strip().lower() != "observe":
        raise ValueError("Digital Avatar mode transitions V1 are OBSERVE only")

    blockers: list[str] = []
    current = session.mode

    if target_mode == current:
        blockers.append("target_mode_already_active")
    elif target_mode == AvatarMeetingMode.SHADOW:
        pass
    else:
        current_index = _MODE_ORDER.index(current)
        target_index = _MODE_ORDER.index(target_mode)
        if target_index != current_index + 1:
            blockers.append("mode_transition_must_be_single_step")

        if not str(evidence.owner_approval_evidence_ref or "").strip():
            blockers.append("owner_approval_evidence_missing")

        if target_mode in {
            AvatarMeetingMode.REPRESENT,
            AvatarMeetingMode.NEGOTIATE,
            AvatarMeetingMode.CLOSE,
        } and not session.disclosure_announced:
            blockers.append("ai_disclosure_not_announced")


        if target_mode in {
            AvatarMeetingMode.NEGOTIATE,
            AvatarMeetingMode.CLOSE,
        } and not str(
            evidence.delegated_authority_evidence_ref or ""
        ).strip():
            blockers.append("delegated_authority_evidence_missing")

        if target_mode == AvatarMeetingMode.CLOSE and not str(
            evidence.commercial_terms_evidence_ref or ""
        ).strip():
            blockers.append("commercial_terms_evidence_missing")

    policy_blockers = tuple(sorted(set(blockers)))
    policy_eligible = not policy_blockers
    execution_blockers = list(policy_blockers)
    execution_blockers.append("runtime_observe_only")

    return AvatarModeTransitionDecision(
        meeting_id=session.meeting_id,
        current_mode=current,
        target_mode=target_mode,
        policy_eligible=policy_eligible,
        execution_allowed=False,
        blockers=tuple(sorted(set(execution_blockers))),
    )
