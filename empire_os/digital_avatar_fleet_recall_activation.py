"""Fleet-scoped pre-execution wrapper for Recall SHADOW activation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from empire_os.digital_avatar_fleet import AvatarFleetRuntimeBinding
from empire_os.digital_avatar_fleet_recall_launch import (
    AvatarFleetRecallLaunchPreparation,
)
from empire_os.recall_shadow_activation import RecallShadowActivationPacket
from empire_os.recall_shadow_join import (
    RecallShadowJoinApproval,
    prepare_recall_shadow_join,
)


@dataclass(frozen=True)
class AvatarFleetRecallActivationPreparation:
    tenant_id: str
    meeting_id: str
    avatar_id: str
    activation_packet: RecallShadowActivationPacket
    approval_evidence_ref: str
    approved_by: str
    region: str
    activation_ready: bool = True
    fleet_scope_verified: bool = True
    live_join_authorized: bool = True
    activation_persisted: bool = False
    provider_call_performed: bool = False
    bot_created: bool = False
    meeting_join_performed: bool = False
    speech_execution: bool = False
    chat_send_execution: bool = False
    commercial_execution: bool = False
    payment_execution: bool = False
    revenue_recognition: bool = False
    execution_authority: str = "shadow_join_only_pending_execution"

    def as_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "meeting_id": self.meeting_id,
            "avatar_id": self.avatar_id,
            "activation_packet": self.activation_packet.as_dict(),
            "approval_evidence_ref": self.approval_evidence_ref,
            "approved_by": self.approved_by,
            "region": self.region,
            "activation_ready": self.activation_ready,
            "fleet_scope_verified": self.fleet_scope_verified,
            "live_join_authorized": self.live_join_authorized,
            "activation_persisted": self.activation_persisted,
            "provider_call_performed": self.provider_call_performed,
            "bot_created": self.bot_created,
            "meeting_join_performed": self.meeting_join_performed,
            "speech_execution": self.speech_execution,
            "chat_send_execution": self.chat_send_execution,
            "commercial_execution": self.commercial_execution,
            "payment_execution": self.payment_execution,
            "revenue_recognition": self.revenue_recognition,
            "execution_authority": self.execution_authority,
        }


def _validate_runtime(runtime: AvatarFleetRuntimeBinding) -> None:
    required = (
        runtime.tenant_id,
        runtime.avatar_id,
        runtime.owner_ref,
        runtime.owner_name,
        runtime.owner_consent_evidence_ref,
    )
    if not all(str(value).strip() for value in required):
        raise ValueError("fleet activation runtime identity required")
    if runtime.runtime_authority != "observe":
        raise ValueError("fleet activation runtime authority must remain observe")
    if runtime.execution_authority != "none":
        raise ValueError("fleet activation runtime execution authority must remain none")
    if (
        runtime.speech_execution_allowed
        or runtime.commercial_execution_allowed
        or runtime.payment_execution_allowed
        or runtime.revenue_recognition_allowed
    ):
        raise ValueError("fleet activation runtime grants forbidden authority")


def _validate_launch(
    *,
    runtime: AvatarFleetRuntimeBinding,
    launch: AvatarFleetRecallLaunchPreparation,
) -> None:
    if launch.tenant_id != runtime.tenant_id:
        raise PermissionError("fleet activation tenant mismatch")
    if launch.avatar_id != runtime.avatar_id:
        raise PermissionError("fleet activation avatar mismatch")
    if launch.meeting_id != launch.bot_plan.meeting_id:
        raise ValueError("fleet activation launch meeting mismatch")
    if launch.avatar_id != launch.bot_plan.avatar_id:
        raise ValueError("fleet activation bot-plan avatar mismatch")
    if launch.avatar_id != launch.session_manifest.identity.avatar_id:
        raise ValueError("fleet activation session avatar mismatch")

    identity = launch.session_manifest.identity
    if identity.owner_name.strip() != runtime.owner_name.strip():
        raise PermissionError("fleet activation owner mismatch")
    if (
        identity.owner_consent_evidence_ref.strip()
        != runtime.owner_consent_evidence_ref.strip()
    ):
        raise PermissionError("fleet activation consent mismatch")

    if not launch.launch_ready:
        raise ValueError("fleet activation requires launch-ready preparation")
    if (
        launch.recommendation_only is not True
        or launch.session_persisted
        or launch.provider_call_performed
        or launch.bot_created
        or launch.meeting_join_performed
        or launch.output_media_start_performed
        or launch.speech_execution_allowed
        or launch.commercial_execution_allowed
        or launch.payment_execution_allowed
        or launch.revenue_recognition_allowed
        or launch.execution_authority != "none"
    ):
        raise ValueError("fleet activation launch contains forbidden execution state")

    plan = launch.bot_plan
    if plan.mode != "SHADOW":
        raise ValueError("fleet activation requires SHADOW bot plan")
    if (
        plan.api_call_allowed
        or plan.live_join_execution
        or plan.output_media_enabled
        or plan.chat_send_enabled
        or plan.speech_execution
        or plan.execution_authority != "none"
    ):
        raise ValueError("fleet activation bot plan grants forbidden authority")


def prepare_avatar_fleet_recall_activation(
    *,
    runtime: AvatarFleetRuntimeBinding,
    launch: AvatarFleetRecallLaunchPreparation,
    approval: RecallShadowJoinApproval,
    region: str,
    now: str,
) -> AvatarFleetRecallActivationPreparation:
    _validate_runtime(runtime)
    _validate_launch(runtime=runtime, launch=launch)

    if approval.approved_by.strip() != runtime.owner_name.strip():
        raise PermissionError("fleet activation approval owner mismatch")
    if approval.meeting_id != launch.meeting_id:
        raise ValueError("fleet activation approval meeting mismatch")

    join_request = prepare_recall_shadow_join(
        plan=launch.bot_plan,
        approval=approval,
        region=region,
        now=now,
    )

    packet = RecallShadowActivationPacket(
        manifest=launch.session_manifest,
        bot_plan=launch.bot_plan,
        join_request=join_request,
    )

    if packet.live_join_performed:
        raise ValueError("fleet activation packet already records live join")
    if (
        packet.speech_execution
        or packet.chat_send_execution
        or packet.commercial_execution
    ):
        raise ValueError("fleet activation packet contains forbidden output execution")
    if packet.execution_authority != "shadow_join_only":
        raise ValueError("fleet activation packet authority invalid")
    if packet.join_request.meeting_id != launch.meeting_id:
        raise ValueError("fleet activation join meeting mismatch")
    if packet.join_request.avatar_id != runtime.avatar_id:
        raise ValueError("fleet activation join avatar mismatch")

    return AvatarFleetRecallActivationPreparation(
        tenant_id=runtime.tenant_id,
        meeting_id=launch.meeting_id,
        avatar_id=runtime.avatar_id,
        activation_packet=packet,
        approval_evidence_ref=approval.approval_evidence_ref,
        approved_by=approval.approved_by,
        region=join_request.region,
    )
