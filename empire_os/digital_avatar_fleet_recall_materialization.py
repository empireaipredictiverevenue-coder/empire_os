"""Tenant-namespaced local materialization for Fleet Recall activation."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from empire_os.digital_avatar_fleet_recall_activation import (
    AvatarFleetRecallActivationPreparation,
)
from empire_os.recall_shadow_activation_store import (
    RecallShadowActivationRecord,
    materialize_recall_shadow_activation,
)


def tenant_scope_key(tenant_id: str) -> str:
    clean = str(tenant_id or "").strip()
    if not clean:
        raise ValueError("fleet materialization tenant_id required")
    digest = sha256(clean.encode("utf-8")).hexdigest()[:24]
    return f"tenant-{digest}"


@dataclass(frozen=True)
class AvatarFleetRecallMaterialization:
    tenant_id: str
    tenant_scope_key: str
    meeting_id: str
    avatar_id: str
    session_root: str
    activation_root: str
    activation_record: RecallShadowActivationRecord
    activation_plan_sha256: str
    materialization_ready: bool = True
    activation_persisted: bool = True
    session_persisted: bool = True
    provider_call_performed: bool = False
    meeting_join_performed: bool = False
    speech_execution: bool = False
    chat_send_execution: bool = False
    commercial_execution: bool = False
    payment_execution: bool = False
    revenue_recognition: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "activation_record": self.activation_record.as_dict(),
        }


def _validate_preparation(
    preparation: AvatarFleetRecallActivationPreparation,
) -> None:
    if not preparation.tenant_id.strip():
        raise ValueError("fleet materialization tenant_id required")
    if not preparation.meeting_id.strip() or not preparation.avatar_id.strip():
        raise ValueError("fleet materialization meeting/avatar required")
    if (
        preparation.activation_ready is not True
        or preparation.fleet_scope_verified is not True
        or preparation.live_join_authorized is not True
    ):
        raise ValueError("fleet materialization requires activation-ready preparation")
    if (
        preparation.activation_persisted
        or preparation.provider_call_performed
        or preparation.bot_created
        or preparation.meeting_join_performed
        or preparation.speech_execution
        or preparation.chat_send_execution
        or preparation.commercial_execution
        or preparation.payment_execution
        or preparation.revenue_recognition
    ):
        raise ValueError("fleet materialization preparation already executed")
    if preparation.execution_authority != "shadow_join_only_pending_execution":
        raise ValueError("fleet materialization preparation authority invalid")

    packet = preparation.activation_packet
    if packet.bot_plan.meeting_id != preparation.meeting_id:
        raise ValueError("fleet materialization packet meeting mismatch")
    if packet.bot_plan.avatar_id != preparation.avatar_id:
        raise ValueError("fleet materialization packet avatar mismatch")
    if packet.live_join_performed:
        raise ValueError("fleet materialization packet already joined")
    if (
        packet.speech_execution
        or packet.chat_send_execution
        or packet.commercial_execution
    ):
        raise ValueError("fleet materialization packet grants forbidden output")


def materialize_avatar_fleet_recall_activation(
    *,
    preparation: AvatarFleetRecallActivationPreparation,
    session_base_root: str | Path,
    activation_base_root: str | Path,
) -> AvatarFleetRecallMaterialization:
    _validate_preparation(preparation)
    scope = tenant_scope_key(preparation.tenant_id)
    session_root = Path(session_base_root).resolve() / scope
    activation_root = Path(activation_base_root).resolve() / scope

    record = materialize_recall_shadow_activation(
        packet=preparation.activation_packet,
        session_root=session_root,
        activation_root=activation_root,
    )

    if record.meeting_id != preparation.meeting_id:
        raise ValueError("fleet materialization record meeting mismatch")
    if record.avatar_id != preparation.avatar_id:
        raise ValueError("fleet materialization record avatar mismatch")
    if record.live_join_performed:
        raise ValueError("fleet materialization record unexpectedly joined")
    if record.provider_api_call_started or record.provider_api_call_performed:
        raise ValueError("fleet materialization record unexpectedly called provider")
    if record.execution_state != "prepared":
        raise ValueError("fleet materialization record state invalid")
    if (
        record.speech_execution
        or record.chat_send_execution
        or record.commercial_execution
        or record.execution_authority != "none"
    ):
        raise ValueError("fleet materialization record grants forbidden authority")

    return AvatarFleetRecallMaterialization(
        tenant_id=preparation.tenant_id,
        tenant_scope_key=scope,
        meeting_id=preparation.meeting_id,
        avatar_id=preparation.avatar_id,
        session_root=str(session_root),
        activation_root=str(activation_root),
        activation_record=record,
        activation_plan_sha256=record.plan_sha256,
    )
