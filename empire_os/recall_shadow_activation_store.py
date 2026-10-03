"""Tamper-evident local persistence for approved Recall SHADOW activation plans."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Mapping

from empire_os.recall_shadow_activation import RecallShadowActivationPacket
from empire_os.recall_shadow_session import save_recall_shadow_session


@dataclass(frozen=True)
class RecallShadowActivationRecord:
    meeting_id: str
    avatar_id: str
    region: str
    plan_sha256: str
    approval_evidence_ref: str
    approved_by: str | None
    approved_at: str | None
    expires_at: str | None
    session_filename: str
    schema_version: str = "empire.recall_shadow_activation.v1"
    mode: str = "SHADOW"
    live_join_prepared: bool = True
    live_join_performed: bool = False
    provider_api_call_started: bool = False
    provider_api_call_performed: bool = False
    execution_state: str = "prepared"
    provider_bot_id: str | None = None
    provider_status: int | None = None
    speech_execution: bool = False
    chat_send_execution: bool = False
    commercial_execution: bool = False
    join_execution_authority: str = "shadow_join_only"
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _canonical_plan(packet: RecallShadowActivationPacket) -> dict[str, Any]:
    authorization = packet.join_request.authorization
    return {
        "meeting_id": packet.bot_plan.meeting_id,
        "avatar_id": packet.bot_plan.avatar_id,
        "region": packet.join_request.region,
        "manifest": packet.manifest.as_dict(),
        "request_body": packet.bot_plan.request_body,
        "approval": {
            "approval_evidence_ref": authorization.approval_evidence_ref,
            "meeting_id": authorization.meeting_id,
            "approved_by": authorization.approved_by,
            "approved_at": authorization.approved_at,
            "expires_at": authorization.expires_at,
            "allow_adhoc": authorization.allow_adhoc,
        },
        "recording_consent_evidence_ref": (
            packet.manifest.recording_consent_evidence_ref
        ),
    }


def activation_plan_sha256(packet: RecallShadowActivationPacket) -> str:
    encoded = json.dumps(
        _canonical_plan(packet),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    tmp = path.parent / f".{path.name}.{os.getpid()}.tmp"
    encoded = (
        json.dumps(payload, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        os.chmod(path, 0o600)
    finally:
        if tmp.exists():
            tmp.unlink()


def materialize_recall_shadow_activation(
    *,
    packet: RecallShadowActivationPacket,
    session_root: str | Path,
    activation_root: str | Path,
) -> RecallShadowActivationRecord:
    if packet.live_join_performed:
        raise ValueError("activation packet already records live join")
    if (
        packet.speech_execution
        or packet.chat_send_execution
        or packet.commercial_execution
    ):
        raise ValueError("SHADOW activation cannot contain output execution")
    if packet.join_request.execution_authority != "shadow_join_only":
        raise ValueError("unexpected SHADOW join authority")

    digest = activation_plan_sha256(packet)
    authorization = packet.join_request.authorization
    session_filename = f"{packet.bot_plan.meeting_id}.json"
    record = RecallShadowActivationRecord(
        meeting_id=packet.bot_plan.meeting_id,
        avatar_id=packet.bot_plan.avatar_id,
        region=packet.join_request.region,
        plan_sha256=digest,
        approval_evidence_ref=authorization.approval_evidence_ref,
        approved_by=authorization.approved_by,
        approved_at=authorization.approved_at,
        expires_at=authorization.expires_at,
        session_filename=session_filename,
    )

    root = Path(activation_root)
    target = root / f"{record.meeting_id}.json"
    if target.is_file():
        try:
            current = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("existing SHADOW activation record unreadable") from exc
        if not isinstance(current, Mapping):
            raise ValueError("existing SHADOW activation record invalid")
        if current.get("plan_sha256") != record.plan_sha256:
            raise ValueError("SHADOW activation record conflict")
        save_recall_shadow_session(
            root=session_root,
            manifest=packet.manifest,
        )
        try:
            return RecallShadowActivationRecord(**dict(current))
        except (TypeError, KeyError) as exc:
            raise ValueError(
                "existing SHADOW activation record schema invalid"
            ) from exc

    save_recall_shadow_session(
        root=session_root,
        manifest=packet.manifest,
    )
    _atomic_json(target, record.as_dict())
    return record
