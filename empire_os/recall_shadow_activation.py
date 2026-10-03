"""Deterministic preflight packet for one governed Recall SHADOW meeting."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from empire_os.digital_avatar import (
    AvatarMeetingMode,
    AvatarMeetingSession,
    DigitalAvatarIdentity,
)
from empire_os.digital_avatar_authority import (
    AvatarCloseProposal,
    AvatarCommercialAuthorityPolicy,
)
from empire_os.meeting_gateway import MeetingPlatform, MeetingSpeakerRole
from empire_os.recall_shadow_bot_plan import (
    RecallShadowBotPlan,
    build_recall_shadow_bot_plan,
)
from empire_os.recall_shadow_join import (
    AuthorizedRecallShadowJoin,
    RecallShadowJoinApproval,
    prepare_recall_shadow_join,
)
from empire_os.recall_shadow_session import RecallShadowSessionManifest


@dataclass(frozen=True)
class RecallShadowActivationPacket:
    manifest: RecallShadowSessionManifest
    bot_plan: RecallShadowBotPlan
    join_request: AuthorizedRecallShadowJoin
    mode: str = "SHADOW"
    live_join_prepared: bool = True
    live_join_performed: bool = False
    speech_execution: bool = False
    chat_send_execution: bool = False
    commercial_execution: bool = False
    execution_authority: str = "shadow_join_only"

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "manifest": self.manifest.as_dict(),
            "bot_plan": self.bot_plan.as_dict(),
            "join_request": self.join_request.as_dict(),
        }


def prepare_recall_shadow_activation(
    *,
    identity: DigitalAvatarIdentity,
    meeting_id: str,
    platform: MeetingPlatform | str,
    meeting_url: str,
    bot_name: str,
    public_realtime_url: str,
    account_name: str,
    objective: str,
    owner_join_approval: RecallShadowJoinApproval,
    region: str,
    now: str,
    recording_consent_evidence_ref: str,
    webhook_verification_evidence_ref: str,
    conversation_id: str | None = None,
    opportunity_id: str | None = None,
    proof_refs: Sequence[str] = (),
    commercial_terms_ref: str | None = None,
    predictive_inputs: Mapping[str, Any] | None = None,
    action_candidates: Sequence[Mapping[str, Any]] = (),
    commercial_policy: AvatarCommercialAuthorityPolicy | None = None,
    close_proposal: AvatarCloseProposal | None = None,
    participant_roles: Mapping[
        str, MeetingSpeakerRole | str
    ] | None = None,
    join_at: str | None = None,
) -> RecallShadowActivationPacket:
    identity.validate()
    try:
        resolved_platform = (
            platform
            if isinstance(platform, MeetingPlatform)
            else MeetingPlatform(str(platform))
        )
    except ValueError as exc:
        raise ValueError("unsupported meeting platform") from exc

    clean_meeting = str(meeting_id or "").strip()
    if not clean_meeting:
        raise ValueError("meeting_id required")


    roles: dict[str, MeetingSpeakerRole] = {}
    for key, value in (participant_roles or {}).items():
        role = (
            value
            if isinstance(value, MeetingSpeakerRole)
            else MeetingSpeakerRole(str(value))
        )
        roles[str(key)] = role

    session = AvatarMeetingSession(
        meeting_id=clean_meeting,
        avatar_id=identity.avatar_id,
        provider="recall",
        mode=AvatarMeetingMode.SHADOW,
        disclosure_announced=False,
        participant_refs=tuple(sorted(roles)),
    )
    manifest = RecallShadowSessionManifest(
        identity=identity,
        session=session,
        account_name=str(account_name or "").strip(),
        objective=str(objective or "").strip(),
        recording_consent_evidence_ref=(
            str(recording_consent_evidence_ref or "").strip()
        ),
        conversation_id=(
            str(conversation_id).strip()
            if conversation_id is not None
            else None
        ),
        opportunity_id=(
            str(opportunity_id).strip()
            if opportunity_id is not None
            else None
        ),
        proof_refs=tuple(str(x) for x in proof_refs if str(x).strip()),
        commercial_terms_ref=(
            str(commercial_terms_ref).strip()
            if commercial_terms_ref is not None
            else None
        ),
        predictive_inputs=dict(predictive_inputs or {}),
        action_candidates=tuple(dict(row) for row in action_candidates),
        commercial_policy=commercial_policy,
        close_proposal=close_proposal,
        participant_roles=roles,
    )
    manifest.validate()


    bot_plan = build_recall_shadow_bot_plan(
        meeting_id=clean_meeting,
        avatar_id=identity.avatar_id,
        platform=resolved_platform,
        bot_name=bot_name,
        meeting_url=meeting_url,
        realtime_webhook_url=public_realtime_url,
        recording_consent_evidence_ref=recording_consent_evidence_ref,
        webhook_verification_evidence_ref=(
            webhook_verification_evidence_ref
        ),
        join_at=join_at,
    )
    join_request = prepare_recall_shadow_join(
        plan=bot_plan,
        approval=owner_join_approval,
        region=region,
        now=now,
    )

    if manifest.session.meeting_id != bot_plan.meeting_id:
        raise ValueError("activation meeting identity mismatch")
    if manifest.identity.avatar_id != bot_plan.avatar_id:
        raise ValueError("activation avatar identity mismatch")

    return RecallShadowActivationPacket(
        manifest=manifest,
        bot_plan=bot_plan,
        join_request=join_request,
    )
