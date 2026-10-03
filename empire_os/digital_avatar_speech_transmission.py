"""One-turn, one-use speech transmission authority for Digital Avatar."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Mapping

from empire_os.digital_avatar import DigitalAvatarIdentity
from empire_os.digital_avatar_speech import (
    AvatarHumanTurnApproval,
    AvatarSpeechRenderTask,
)
from empire_os.digital_avatar_voice_sidecar import AvatarVoiceRenderArtifact


def _dt(value: str) -> datetime:
    raw = str(value or "").strip()
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("speech transmission timestamps must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("speech transmission timestamps must include timezone")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class AvatarSpeechTransmissionTicket:
    ticket_id: str
    meeting_id: str
    avatar_id: str
    bot_id: str
    render_id: str
    text_sha256: str
    audio_sha256: str
    approval_evidence_ref: str
    approved_by: str
    expires_at: str
    pcm_bytes: int
    sample_rate: int
    one_time: bool = True
    speech_transmission_allowed: bool = True
    commercial_execution_allowed: bool = False
    execution_authority: str = "approved_turn_audio_only"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _ticket_id(
    *,
    task: AvatarSpeechRenderTask,
    artifact: AvatarVoiceRenderArtifact,
    bot_id: str,
    approval: AvatarHumanTurnApproval,
) -> str:
    material = "|".join((
        task.meeting_id,
        task.avatar_id,
        bot_id,
        task.text_sha256,
        artifact.audio_sha256,
        approval.approval_evidence_ref,
    )).encode("utf-8")
    return "avatar-speech:" + sha256(material).hexdigest()


def authorize_avatar_speech_transmission(
    *,
    identity: DigitalAvatarIdentity,
    task: AvatarSpeechRenderTask,
    artifact: AvatarVoiceRenderArtifact,
    approval: AvatarHumanTurnApproval,
    presence_state: Mapping[str, Any],
    now: datetime | None = None,
) -> AvatarSpeechTransmissionTicket:
    identity.validate()
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    if presence_state.get("presence_active") is not True:
        raise ValueError("Digital Avatar presence is not active")
    if presence_state.get("output_media_start_performed") is not True:
        raise ValueError("Output Media start evidence missing")
    if str(presence_state.get("meeting_id") or "") != task.meeting_id:
        raise ValueError("presence/speech meeting mismatch")
    if str(presence_state.get("avatar_id") or "") != task.avatar_id:
        raise ValueError("presence/speech avatar mismatch")
    bot_id = str(presence_state.get("bot_id") or "").strip()
    if not bot_id:
        raise ValueError("presence bot identity missing")
    if presence_state.get("speech_execution_allowed") is not False:
        raise ValueError("presence state unexpectedly grants speech")
    if str(presence_state.get("execution_authority") or "") != (
        "copilot_presence_start_only"
    ):
        raise ValueError("presence state authority invalid")

    if task.avatar_id != identity.avatar_id:
        raise ValueError("speech task/avatar identity mismatch")
    if task.meeting_transmission_allowed:
        raise ValueError("speech render task unexpectedly grants transmission")
    if task.speech_execution_allowed:
        raise ValueError("speech render task unexpectedly grants speech execution")
    if artifact.text_sha256 != task.text_sha256:
        raise ValueError("render artifact text fingerprint mismatch")
    if artifact.meeting_transmission_performed:
        raise ValueError("render artifact already transmitted")
    if artifact.speech_execution_performed:
        raise ValueError("render artifact already executed as speech")
    if not artifact.audio_sha256 or artifact.pcm_bytes <= 0:
        raise ValueError("render artifact audio evidence incomplete")

    if approval.meeting_id != task.meeting_id:
        raise ValueError("speech approval meeting mismatch")
    if approval.avatar_id != task.avatar_id:
        raise ValueError("speech approval avatar mismatch")
    if approval.approved_by.strip() != identity.owner_name.strip():
        raise ValueError("speech approval owner mismatch")
    if approval.approval_evidence_ref != task.approval_evidence_ref:
        raise ValueError("speech approval evidence mismatch")
    if approval.approved_text_sha256 != task.text_sha256:
        raise ValueError("speech approval text fingerprint mismatch")
    approved = _dt(approval.approved_at)
    expires = _dt(approval.expires_at)
    if expires <= approved:
        raise ValueError("speech approval expiry invalid")
    if current < approved or current >= expires:
        raise ValueError("speech approval not active")

    return AvatarSpeechTransmissionTicket(
        ticket_id=_ticket_id(
            task=task,
            artifact=artifact,
            bot_id=bot_id,
            approval=approval,
        ),
        meeting_id=task.meeting_id,
        avatar_id=task.avatar_id,
        bot_id=bot_id,
        render_id=artifact.render_id,
        text_sha256=task.text_sha256,
        audio_sha256=artifact.audio_sha256,
        approval_evidence_ref=approval.approval_evidence_ref,
        approved_by=approval.approved_by,
        expires_at=approval.expires_at,
        pcm_bytes=artifact.pcm_bytes,
        sample_rate=artifact.sample_rate,
    )


def materialize_speech_transmission_ticket(
    *,
    root: str | Path,
    ticket: AvatarSpeechTransmissionTicket,
) -> Path:
    target_root = Path(root)
    target_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(target_root, 0o700)
    safe_name = ticket.ticket_id.replace(":", "__")
    target = target_root / f"{safe_name}.json"
    record = {
        "schema_version": "empire.avatar_speech_transmission.v1",
        **ticket.as_dict(),
        "state": "authorized",
        "consumed": False,
        "raw_audio_persisted": False,
    }
    if target.is_file():
        try:
            current = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("speech transmission ticket unreadable") from exc
        if not isinstance(current, Mapping):
            raise ValueError("speech transmission ticket invalid")
        if current.get("audio_sha256") != ticket.audio_sha256:
            raise ValueError("speech transmission ticket conflict")
        return target

    tmp = target_root / f".{safe_name}.{os.getpid()}.tmp"
    encoded = (
        json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
        os.chmod(target, 0o600)
    finally:
        if tmp.exists():
            tmp.unlink()
    return target


def claim_speech_transmission_ticket(
    *,
    path: str | Path,
    ticket: AvatarSpeechTransmissionTicket,
    now: datetime | None = None,
) -> dict[str, Any]:
    target = Path(path)
    lock = target.parent / f".{target.name}.claim.lock"
    try:
        lock_fd = os.open(
            lock,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except FileExistsError as exc:
        raise ValueError("speech transmission ticket claim already in progress") from exc

    try:
        with os.fdopen(lock_fd, "wb") as handle:
            handle.write(ticket.ticket_id.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())

        try:
            record = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("speech transmission ticket unreadable") from exc
        if not isinstance(record, dict):
            raise ValueError("speech transmission ticket invalid")
        if record.get("schema_version") != "empire.avatar_speech_transmission.v1":
            raise ValueError("speech transmission ticket schema invalid")
        if record.get("ticket_id") != ticket.ticket_id:
            raise ValueError("speech transmission ticket identity mismatch")
        if record.get("audio_sha256") != ticket.audio_sha256:
            raise ValueError("speech transmission audio mismatch")
        if record.get("state") != "authorized" or record.get("consumed") is not False:
            raise ValueError("speech transmission ticket already claimed")

        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        if current >= _dt(ticket.expires_at):
            raise ValueError("speech transmission ticket expired")

        claimed = {
            **record,
            "state": "in_flight",
            "consumed": True,
            "claimed_at": current.isoformat(),
        }
        tmp = target.parent / f".{target.name}.{os.getpid()}.claim.tmp"
        encoded = (
            json.dumps(claimed, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, target)
            os.chmod(target, 0o600)
        finally:
            if tmp.exists():
                tmp.unlink()
        return claimed
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def finalize_speech_transmission_ticket(
    *,
    path: str | Path,
    ticket: AvatarSpeechTransmissionTicket,
    performed: bool,
    now: datetime | None = None,
    error_code: str | None = None,
) -> dict[str, Any]:
    target = Path(path)
    try:
        record = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("speech transmission ticket unreadable") from exc
    if not isinstance(record, dict):
        raise ValueError("speech transmission ticket invalid")
    if record.get("ticket_id") != ticket.ticket_id:
        raise ValueError("speech transmission ticket identity mismatch")
    if record.get("state") != "in_flight" or record.get("consumed") is not True:
        raise ValueError("speech transmission ticket is not in flight")

    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    state = "completed" if performed else "reconciliation_required"
    finalized = {
        **record,
        "state": state,
        "speech_transmission_performed": bool(performed),
        "finalized_at": current.isoformat(),
        "error_code": (
            str(error_code or "").strip() or None
            if not performed
            else None
        ),
    }
    tmp = target.parent / f".{target.name}.{os.getpid()}.finalize.tmp"
    encoded = (
        json.dumps(finalized, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
        os.chmod(target, 0o600)
    finally:
        if tmp.exists():
            tmp.unlink()
    return finalized


def validate_inflight_speech_transmission_record(
    *,
    path: str | Path,
    ticket_id: str,
    meeting_id: str,
    avatar_id: str,
    bot_id: str,
    audio_sha256: str,
    pcm_bytes: int,
    sample_rate: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate one already-claimed ticket before Presence receives PCM."""
    target = Path(path)
    try:
        record = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("speech transmission ticket unreadable") from exc
    if not isinstance(record, dict):
        raise ValueError("speech transmission ticket invalid")
    if record.get("schema_version") != "empire.avatar_speech_transmission.v1":
        raise ValueError("speech transmission ticket schema invalid")
    expected = (
        ("ticket", ticket_id, record.get("ticket_id")),
        ("meeting", meeting_id, record.get("meeting_id")),
        ("avatar", avatar_id, record.get("avatar_id")),
        ("bot", bot_id, record.get("bot_id")),
        ("audio", audio_sha256, record.get("audio_sha256")),
    )
    for label, wanted, actual in expected:
        if str(wanted or "").strip() != str(actual or "").strip():
            raise ValueError(f"speech transmission {label} mismatch")
    if int(record.get("pcm_bytes") or 0) != int(pcm_bytes):
        raise ValueError("speech transmission pcm size mismatch")
    if int(record.get("sample_rate") or 0) != int(sample_rate):
        raise ValueError("speech transmission sample rate mismatch")
    if record.get("state") != "in_flight" or record.get("consumed") is not True:
        raise ValueError("speech transmission ticket is not in flight")
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    expires_at = _dt(str(record.get("expires_at") or ""))
    if current >= expires_at:
        raise ValueError("speech transmission ticket expired")
    if record.get("speech_transmission_allowed") is not True:
        raise ValueError("speech transmission authority missing")
    if record.get("commercial_execution_allowed") is not False:
        raise ValueError("speech ticket grants forbidden commercial authority")
    if str(record.get("execution_authority") or "") != (
        "approved_turn_audio_only"
    ):
        raise ValueError("speech ticket execution authority invalid")
    return record


def finalize_inflight_speech_transmission_record(
    *,
    path: str | Path,
    ticket_id: str,
    performed: bool,
    now: datetime | None = None,
    error_code: str | None = None,
) -> dict[str, Any]:
    """Finalize an already-claimed ticket using the persisted record only."""
    target = Path(path)
    try:
        record = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("speech transmission ticket unreadable") from exc
    if not isinstance(record, dict):
        raise ValueError("speech transmission ticket invalid")
    if record.get("schema_version") != "empire.avatar_speech_transmission.v1":
        raise ValueError("speech transmission ticket schema invalid")
    if str(record.get("ticket_id") or "") != str(ticket_id or "").strip():
        raise ValueError("speech transmission ticket identity mismatch")
    if record.get("state") != "in_flight" or record.get("consumed") is not True:
        raise ValueError("speech transmission ticket is not in flight")
    if record.get("speech_transmission_allowed") is not True:
        raise ValueError("speech transmission authority missing")
    if record.get("commercial_execution_allowed") is not False:
        raise ValueError("speech ticket grants forbidden commercial authority")
    if str(record.get("execution_authority") or "") != (
        "approved_turn_audio_only"
    ):
        raise ValueError("speech ticket execution authority invalid")

    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    state = "completed" if performed else "reconciliation_required"
    finalized = {
        **record,
        "state": state,
        "speech_transmission_performed": bool(performed),
        "finalized_at": current.isoformat(),
        "error_code": (
            None
            if performed
            else (str(error_code or "").strip() or "unknown_delivery_error")
        ),
    }
    tmp = target.parent / f".{target.name}.{os.getpid()}.record-finalize.tmp"
    encoded = (
        json.dumps(finalized, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
        os.chmod(target, 0o600)
    finally:
        if tmp.exists():
            tmp.unlink()
    return finalized
