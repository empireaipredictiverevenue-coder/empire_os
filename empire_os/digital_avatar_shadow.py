"""Private shadow-mode guidance for Empire Digital Avatar."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from empire_os.digital_avatar import AvatarMeetingSession, DigitalAvatarIdentity
from empire_os.digital_avatar_authority import (
    AvatarCloseProposal,
    AvatarCommercialAuthorityPolicy,
    assess_avatar_commercial_authority,
)
from empire_os.digital_avatar_strategy import (
    AvatarMeetingStrategyPacket,
    build_avatar_meeting_strategy,
)
from empire_os.meeting_gateway import ShadowMeetingState


@dataclass(frozen=True)
class AvatarShadowGuidance:
    meeting_id: str
    avatar_id: str
    latest_buyer_utterance: Mapping[str, Any] | None
    recommended_action: Mapping[str, Any]
    strategy: AvatarMeetingStrategyPacket
    commercial_authority: Mapping[str, Any] | None
    human_takeover_required: bool
    blockers: tuple[str, ...]
    mode: str = "OBSERVE"
    private_to_owner: bool = True
    speech_execution: bool = False
    meeting_action_execution: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["recommended_action"] = dict(self.recommended_action)
        data["strategy"] = self.strategy.as_dict()
        data["commercial_authority"] = (
            dict(self.commercial_authority)
            if isinstance(self.commercial_authority, Mapping)
            else None
        )
        return data


def build_shadow_guidance(
    *,
    identity: DigitalAvatarIdentity,
    session: AvatarMeetingSession,
    state: ShadowMeetingState,
    account_name: str,
    objective: str,
    proof_refs: Sequence[str] = (),
    commercial_terms_ref: str | None = None,
    predictive_inputs: Mapping[str, Any] | None = None,
    action_candidates: Sequence[Mapping[str, Any]] = (),
    commercial_policy: AvatarCommercialAuthorityPolicy | None = None,
    close_proposal: AvatarCloseProposal | None = None,
) -> AvatarShadowGuidance:
    identity.validate()
    session.validate()

    if state.meeting_id != session.meeting_id:
        raise ValueError("shadow state/session meeting mismatch")
    if state.avatar_id != identity.avatar_id:
        raise ValueError("shadow state/avatar identity mismatch")
    if not state.private_guidance_only:
        raise ValueError("shadow guidance must remain private to owner")
    if state.speech_execution or state.meeting_action_execution:
        raise ValueError("shadow state cannot contain meeting execution")

    latest = state.latest_buyer_utterance
    signal_summary = None
    signal_refs: tuple[str, ...] = ()
    blockers: list[str] = []
    if isinstance(latest, Mapping):
        text = str(latest.get("text") or "").strip()
        evidence_ref = str(latest.get("evidence_ref") or "").strip()
        if text and evidence_ref:
            signal_summary = f"Observed buyer utterance: {text}"
            signal_refs = (evidence_ref,)
        else:
            blockers.append("latest_buyer_utterance_incomplete")
    else:
        blockers.append("buyer_utterance_not_observed")


    strategy = build_avatar_meeting_strategy(
        identity=identity,
        session=session,
        account_name=account_name,
        objective=objective,
        buyer_signal_summary=signal_summary,
        buyer_signal_evidence_refs=signal_refs,
        proof_refs=proof_refs,
        commercial_terms_ref=commercial_terms_ref,
        predictive_inputs=predictive_inputs,
        action_candidates=action_candidates,
    )
    blockers.extend(strategy.blockers)

    recommendation = (
        dict(strategy.next_best_action)
        if isinstance(strategy.next_best_action, Mapping)
        else {}
    )
    if not recommendation:
        blockers.append("private_next_action_unavailable")

    commercial_authority = None
    human_takeover_required = False
    if (commercial_policy is None) != (close_proposal is None):
        blockers.append("commercial_authority_context_incomplete")
        human_takeover_required = True
    elif commercial_policy is not None and close_proposal is not None:
        decision = assess_avatar_commercial_authority(
            policy=commercial_policy,
            proposal=close_proposal,
        )
        commercial_authority = decision.as_dict()
        human_takeover_required = decision.human_takeover_required
        if human_takeover_required:
            blockers.append("commercial_human_takeover_required")

    return AvatarShadowGuidance(
        meeting_id=session.meeting_id,
        avatar_id=identity.avatar_id,
        latest_buyer_utterance=dict(latest) if isinstance(latest, Mapping) else None,
        recommended_action=recommendation,
        strategy=strategy,
        commercial_authority=commercial_authority,
        human_takeover_required=human_takeover_required,
        blockers=tuple(sorted(set(blockers))),
    )
