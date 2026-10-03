"""Tenant-scoped non-executing Recall launch preparation for Clone Fleet."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from empire_os.digital_avatar import (
    AvatarMeetingMode,
    AvatarMeetingSession,
    DigitalAvatarIdentity,
)
from empire_os.digital_avatar_fleet import AvatarFleetRuntimeBinding
from empire_os.digital_avatar_fleet_dispatch import AvatarFleetDispatchDecision
from empire_os.meeting_gateway import MeetingPlatform, MeetingSpeakerRole
from empire_os.recall_shadow_bot_plan import (
    RecallShadowBotPlan,
    build_recall_shadow_bot_plan,
)
from empire_os.recall_shadow_session import RecallShadowSessionManifest


@dataclass(frozen=True)
class AvatarFleetRecallLaunchPreparation:
    tenant_id: str
    meeting_id: str
    avatar_id: str
    bot_plan: RecallShadowBotPlan
    session_manifest: RecallShadowSessionManifest
    recording_consent_evidence_ref: str
    webhook_verification_evidence_ref: str
    launch_ready: bool = True
    ai_disclosure_required: bool = True
    disclosure_announced: bool = False
    recommendation_only: bool = True
    session_persisted: bool = False
    provider_call_performed: bool = False
    bot_created: bool = False
    meeting_join_performed: bool = False
    output_media_start_performed: bool = False
    speech_execution_allowed: bool = False
    commercial_execution_allowed: bool = False
    payment_execution_allowed: bool = False
    revenue_recognition_allowed: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "meeting_id": self.meeting_id,
            "avatar_id": self.avatar_id,
            "bot_plan": self.bot_plan.as_dict(),
            "session_manifest": self.session_manifest.as_dict(),
            "recording_consent_evidence_ref": (
                self.recording_consent_evidence_ref
            ),
            "webhook_verification_evidence_ref": (
                self.webhook_verification_evidence_ref
            ),
            "launch_ready": self.launch_ready,
            "ai_disclosure_required": self.ai_disclosure_required,
            "disclosure_announced": self.disclosure_announced,
            "recommendation_only": self.recommendation_only,
            "session_persisted": self.session_persisted,
            "provider_call_performed": self.provider_call_performed,
            "bot_created": self.bot_created,
            "meeting_join_performed": self.meeting_join_performed,
            "output_media_start_performed": self.output_media_start_performed,
            "speech_execution_allowed": self.speech_execution_allowed,
            "commercial_execution_allowed": self.commercial_execution_allowed,
            "payment_execution_allowed": self.payment_execution_allowed,
            "revenue_recognition_allowed": self.revenue_recognition_allowed,
            "execution_authority": self.execution_authority,
        }


def _validate_runtime(runtime: AvatarFleetRuntimeBinding) -> None:
    required = (
        runtime.tenant_id,
        runtime.avatar_id,
        runtime.owner_ref,
        runtime.owner_name,
        runtime.membership_user_id,
        runtime.membership_role,
        runtime.owner_consent_evidence_ref,
    )
    if not all(str(value).strip() for value in required):
        raise ValueError("launch runtime identity/tenant fields required")
    if runtime.runtime_authority != "observe":
        raise ValueError("launch runtime authority must remain observe")
    if runtime.execution_authority != "none":
        raise ValueError("launch runtime execution authority must remain none")
    if (
        runtime.speech_execution_allowed
        or runtime.commercial_execution_allowed
        or runtime.payment_execution_allowed
        or runtime.revenue_recognition_allowed
    ):
        raise ValueError("launch runtime grants forbidden authority")


def _validate_dispatch(
    *,
    runtime: AvatarFleetRuntimeBinding,
    dispatch: AvatarFleetDispatchDecision,
) -> None:
    if dispatch.tenant_id != runtime.tenant_id:
        raise PermissionError("launch dispatch/runtime tenant mismatch")
    if dispatch.selected_avatar_id != runtime.avatar_id:
        raise PermissionError("launch dispatch/runtime avatar mismatch")
    if not dispatch.dispatch_ready:
        raise ValueError("launch requires dispatch-ready clone")
    if dispatch.requested_mode != AvatarMeetingMode.SHADOW.value:
        raise ValueError("Recall launch preparation requires SHADOW mode")
    if (
        dispatch.recommendation_only is not True
        or dispatch.reservation_persisted
        or dispatch.provider_call_performed
        or dispatch.calendar_invite_sent
        or dispatch.meeting_join_performed
        or dispatch.speech_execution_allowed
        or dispatch.commercial_execution_allowed
        or dispatch.payment_execution_allowed
        or dispatch.execution_authority != "none"
    ):
        raise ValueError("launch dispatch grants forbidden execution authority")


def _validate_identity(
    *,
    runtime: AvatarFleetRuntimeBinding,
    identity: DigitalAvatarIdentity,
) -> None:
    identity.validate()
    if identity.avatar_id != runtime.avatar_id:
        raise PermissionError("launch runtime/identity avatar mismatch")
    if identity.owner_name.strip() != runtime.owner_name.strip():
        raise PermissionError("launch runtime/identity owner mismatch")
    if (
        identity.owner_consent_evidence_ref.strip()
        != runtime.owner_consent_evidence_ref.strip()
    ):
        raise PermissionError("launch runtime/identity consent mismatch")


def prepare_avatar_fleet_recall_launch(
    *,
    runtime: AvatarFleetRuntimeBinding,
    dispatch: AvatarFleetDispatchDecision,
    identity: DigitalAvatarIdentity,
    platform: MeetingPlatform,
    meeting_url: str,
    realtime_webhook_url: str,
    recording_consent_evidence_ref: str,
    webhook_verification_evidence_ref: str,
    account_name: str,
    objective: str,
    join_at: str | None = None,
    conversation_id: str | None = None,
    opportunity_id: str | None = None,
    proof_refs: Sequence[str] = (),
    commercial_terms_ref: str | None = None,
    predictive_inputs: Mapping[str, Any] | None = None,
    action_candidates: Sequence[Mapping[str, Any]] = (),
    participant_roles: Mapping[str, MeetingSpeakerRole] | None = None,
) -> AvatarFleetRecallLaunchPreparation:
    _validate_runtime(runtime)
    _validate_dispatch(runtime=runtime, dispatch=dispatch)
    _validate_identity(runtime=runtime, identity=identity)

    session = AvatarMeetingSession(
        meeting_id=dispatch.meeting_id,
        avatar_id=runtime.avatar_id,
        provider="recall.ai",
        mode=AvatarMeetingMode.SHADOW,
        disclosure_announced=False,
    )
    session.validate()

    manifest = RecallShadowSessionManifest(
        identity=identity,
        session=session,
        account_name=str(account_name or "").strip(),
        objective=str(objective or "").strip(),
        recording_consent_evidence_ref=str(
            recording_consent_evidence_ref or ""
        ).strip(),
        conversation_id=conversation_id,
        opportunity_id=opportunity_id,
        proof_refs=tuple(
            str(value).strip()
            for value in proof_refs
            if str(value).strip()
        ),
        commercial_terms_ref=commercial_terms_ref,
        predictive_inputs=dict(predictive_inputs or {}),
        action_candidates=tuple(dict(row) for row in action_candidates),
        participant_roles=(
            dict(participant_roles)
            if participant_roles is not None
            else None
        ),
    )
    manifest.validate()

    plan = build_recall_shadow_bot_plan(
        meeting_id=dispatch.meeting_id,
        avatar_id=runtime.avatar_id,
        platform=platform,
        bot_name=identity.display_name,
        meeting_url=meeting_url,
        realtime_webhook_url=realtime_webhook_url,
        recording_consent_evidence_ref=(
            recording_consent_evidence_ref
        ),
        webhook_verification_evidence_ref=(
            webhook_verification_evidence_ref
        ),
        join_at=join_at,
    )

    if plan.meeting_id != manifest.session.meeting_id:
        raise ValueError("launch plan/session meeting mismatch")
    if plan.avatar_id != manifest.session.avatar_id:
        raise ValueError("launch plan/session avatar mismatch")
    if plan.api_call_allowed or plan.live_join_execution:
        raise ValueError("launch bot plan unexpectedly grants execution")
    if plan.output_media_enabled or plan.chat_send_enabled or plan.speech_execution:
        raise ValueError("launch bot plan unexpectedly enables output")
    if plan.execution_authority != "none":
        raise ValueError("launch bot plan execution authority invalid")

    return AvatarFleetRecallLaunchPreparation(
        tenant_id=runtime.tenant_id,
        meeting_id=dispatch.meeting_id,
        avatar_id=runtime.avatar_id,
        bot_plan=plan,
        session_manifest=manifest,
        recording_consent_evidence_ref=(
            str(recording_consent_evidence_ref or "").strip()
        ),
        webhook_verification_evidence_ref=(
            str(webhook_verification_evidence_ref or "").strip()
        ),
    )
