"""Tenant-scoped front door to canonical one-time Recall SHADOW execution."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from empire_os.digital_avatar_fleet_recall_activation import (
    AvatarFleetRecallActivationPreparation,
)
from empire_os.digital_avatar_fleet_recall_materialization import (
    AvatarFleetRecallMaterialization,
    tenant_scope_key,
)
from empire_os.recall_shadow_activation_store import activation_plan_sha256
from empire_os.recall_shadow_execution import (
    execute_materialized_recall_shadow_activation,
)


@dataclass(frozen=True)
class AvatarFleetRecallExecutionResult:
    tenant_id: str
    meeting_id: str
    avatar_id: str
    tenant_scope_key: str
    bot_id: str
    provider_status: int
    activation_plan_sha256: str
    execution_state: str
    provider_call_performed: bool
    meeting_join_performed: bool
    speech_execution: bool = False
    chat_send_execution: bool = False
    commercial_execution: bool = False
    payment_execution: bool = False
    revenue_recognition: bool = False
    execution_authority: str = "shadow_join_only_completed"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _validate_scope(
    *,
    preparation: AvatarFleetRecallActivationPreparation,
    materialization: AvatarFleetRecallMaterialization,
) -> None:
    if preparation.tenant_id != materialization.tenant_id:
        raise PermissionError("fleet execution tenant mismatch")
    if preparation.meeting_id != materialization.meeting_id:
        raise ValueError("fleet execution meeting mismatch")
    if preparation.avatar_id != materialization.avatar_id:
        raise PermissionError("fleet execution avatar mismatch")

    expected_scope = tenant_scope_key(preparation.tenant_id)
    if materialization.tenant_scope_key != expected_scope:
        raise ValueError("fleet execution tenant scope mismatch")
    if Path(materialization.activation_root).name != expected_scope:
        raise ValueError("fleet execution activation root scope mismatch")

    expected_hash = activation_plan_sha256(preparation.activation_packet)
    if materialization.activation_plan_sha256 != expected_hash:
        raise ValueError("fleet execution activation fingerprint mismatch")
    if materialization.activation_record.plan_sha256 != expected_hash:
        raise ValueError("fleet execution materialized record fingerprint mismatch")

    record = materialization.activation_record
    if record.execution_state != "prepared":
        raise ValueError("fleet execution materialization is not prepared")
    if (
        record.provider_api_call_started
        or record.provider_api_call_performed
        or record.live_join_performed
    ):
        raise ValueError("fleet execution materialization already executed")
    if (
        record.speech_execution
        or record.chat_send_execution
        or record.commercial_execution
        or record.execution_authority != "none"
    ):
        raise ValueError("fleet execution materialization grants forbidden authority")


def execute_avatar_fleet_recall_activation(
    *,
    preparation: AvatarFleetRecallActivationPreparation,
    materialization: AvatarFleetRecallMaterialization,
    api_key: str,
    live_execution_requested: bool = False,
    transport=None,
    sleeper: Callable[[float], None] | None = None,
    now: datetime | None = None,
    timeout_s: float = 20.0,
    max_attempts: int = 10,
) -> AvatarFleetRecallExecutionResult:
    if live_execution_requested is not True:
        raise PermissionError("explicit live Recall execution request required")
    _validate_scope(
        preparation=preparation,
        materialization=materialization,
    )

    kwargs: dict[str, Any] = {
        "packet": preparation.activation_packet,
        "activation_root": materialization.activation_root,
        "api_key": api_key,
        "transport": transport,
        "now": now,
        "timeout_s": timeout_s,
        "max_attempts": max_attempts,
    }
    if sleeper is not None:
        kwargs["sleeper"] = sleeper

    result = execute_materialized_recall_shadow_activation(**kwargs)

    if result.get("execution_state") != "completed":
        raise RuntimeError("fleet Recall execution did not complete")
    bot_id = str(result.get("bot_id") or "").strip()
    if not bot_id:
        raise RuntimeError("fleet Recall execution missing bot id")
    if result.get("live_join_performed") is not True:
        raise RuntimeError("fleet Recall execution did not request meeting join")
    if result.get("speech_execution") is not False:
        raise RuntimeError("fleet Recall execution unexpectedly enabled speech")
    if result.get("chat_execution") is not False:
        raise RuntimeError("fleet Recall execution unexpectedly enabled chat")
    if result.get("commercial_execution") is not False:
        raise RuntimeError("fleet Recall execution unexpectedly enabled commercial action")

    return AvatarFleetRecallExecutionResult(
        tenant_id=preparation.tenant_id,
        meeting_id=preparation.meeting_id,
        avatar_id=preparation.avatar_id,
        tenant_scope_key=materialization.tenant_scope_key,
        bot_id=bot_id,
        provider_status=int(result.get("provider_status") or 0),
        activation_plan_sha256=str(
            result.get("activation_plan_sha256") or ""
        ),
        execution_state="completed",
        provider_call_performed=True,
        meeting_join_performed=True,
    )
