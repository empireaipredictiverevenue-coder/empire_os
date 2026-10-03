"""Founder-safe aggregate for Recall lifecycle + private guidance."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping

_MEETING_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")


def validate_meeting_id(value: str) -> str:
    clean = str(value or "").strip()
    if not _MEETING_ID_RE.fullmatch(clean):
        raise ValueError("invalid meeting_id")
    return clean


def _load_optional(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid meeting state source: {path.name}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"meeting state source must be object: {path.name}")
    return payload


@dataclass(frozen=True)
class RecallMeetingStateSnapshot:
    meeting_id: str
    avatar_id: str | None
    lifecycle_status: str | None
    lifecycle_sub_code: str | None
    joined_meeting: bool
    currently_in_call: bool
    waiting_room: bool
    recording_active: bool
    terminal: bool
    fatal: bool
    observation_count: int
    latest_buyer_utterance: Mapping[str, Any] | None
    recommended_action: Mapping[str, Any] | None
    response_task: Mapping[str, Any] | None
    close_readiness: Mapping[str, Any] | None
    conversational_close_ready: bool
    binding_execution_allowed: bool
    human_takeover_required: bool
    blockers: tuple[str, ...]
    mode: str = "OBSERVE"
    private_to_owner: bool = True
    speech_execution: bool = False
    chat_execution: bool = False
    commercial_execution: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_recall_meeting_state_snapshot(
    *,
    meeting_id: str,
    guidance_root: str | Path,
    runtime_state_root: str | Path,
    close_readiness_root: str | Path | None = None,
) -> RecallMeetingStateSnapshot:
    clean_id = validate_meeting_id(meeting_id)
    guidance = _load_optional(Path(guidance_root) / f"{clean_id}.json")
    runtime = _load_optional(Path(runtime_state_root) / f"{clean_id}.json")
    close_readiness = (
        _load_optional(Path(close_readiness_root) / f"{clean_id}.json")
        if close_readiness_root is not None
        else None
    )
    if guidance is None and runtime is None and close_readiness is None:
        raise ValueError("meeting state unavailable")

    blockers: list[str] = []
    avatar_id = None
    lifecycle_status = None
    lifecycle_sub_code = None
    joined = current = waiting = recording = terminal = fatal = False

    if runtime is None:
        blockers.append("lifecycle_not_observed")
    else:
        if runtime.get("truth_class") != "VERIFIED":
            raise ValueError("runtime state must be VERIFIED")
        if str(runtime.get("execution_authority") or "").lower() != "none":
            raise ValueError("runtime state grants forbidden authority")
        if runtime.get("polling_performed") is not False:
            raise ValueError("runtime state polling invariant violated")
        if runtime.get("speech_execution") is not False:
            raise ValueError("runtime state speech invariant violated")
        if runtime.get("commercial_execution") is not False:
            raise ValueError("runtime state commercial invariant violated")
        avatar_id = str(runtime.get("avatar_id") or "").strip() or None
        lifecycle_status = str(runtime.get("status_code") or "").strip() or None
        lifecycle_sub_code = str(runtime.get("sub_code") or "").strip() or None
        joined = bool(runtime.get("joined_meeting"))
        current = bool(runtime.get("currently_in_call"))
        waiting = bool(runtime.get("waiting_room"))
        recording = bool(runtime.get("recording_active"))
        terminal = bool(runtime.get("terminal"))
        fatal = bool(runtime.get("fatal"))

    observation_count = 0
    latest_buyer = recommended_action = response_task = None
    human_takeover = False

    if guidance is None:
        blockers.append("private_guidance_not_available")
    else:
        if str(guidance.get("execution_authority") or "").lower() != "none":
            raise ValueError("guidance grants forbidden authority")
        if guidance.get("private_to_owner") is not True:
            raise ValueError("guidance privacy invariant violated")
        if guidance.get("speech_execution") is not False:
            raise ValueError("guidance speech invariant violated")
        guidance_avatar = str(guidance.get("avatar_id") or "").strip() or None
        if avatar_id and guidance_avatar and avatar_id != guidance_avatar:
            raise ValueError("guidance/runtime avatar identity mismatch")
        avatar_id = avatar_id or guidance_avatar
        observation_count = int(guidance.get("observation_count") or 0)
        body = guidance.get("guidance")
        if isinstance(body, Mapping):
            latest = body.get("latest_buyer_utterance")
            latest_buyer = dict(latest) if isinstance(latest, Mapping) else None
            action = body.get("recommended_action")
            recommended_action = dict(action) if isinstance(action, Mapping) and action else None
            human_takeover = bool(body.get("human_takeover_required"))
            blockers.extend(str(x) for x in (body.get("blockers") or ()))
        task = guidance.get("response_task")
        response_task = dict(task) if isinstance(task, Mapping) else None

    close_body = None
    conversational_close_ready = False
    binding_execution_allowed = False
    if close_readiness is not None:
        if close_readiness.get("meeting_id") != clean_id:
            raise ValueError("close readiness meeting identity mismatch")
        close_avatar = str(
            close_readiness.get("avatar_id") or ""
        ).strip() or None
        if avatar_id and close_avatar and avatar_id != close_avatar:
            raise ValueError("close readiness avatar identity mismatch")
        avatar_id = avatar_id or close_avatar
        if close_readiness.get("private_to_owner") is not True:
            raise ValueError("close readiness privacy invariant violated")
        for field in (
            "speech_execution",
            "commercial_execution",
            "payment_execution",
        ):
            if close_readiness.get(field) is not False:
                raise ValueError(
                    f"close readiness {field} invariant violated"
                )
        if str(
            close_readiness.get("execution_authority") or ""
        ).strip().lower() != "none":
            raise ValueError("close readiness grants forbidden authority")
        if close_readiness.get("binding_execution_allowed") is not False:
            raise ValueError(
                "close readiness binding execution invariant violated"
            )
        close_body = dict(close_readiness)
        conversational_close_ready = bool(
            close_readiness.get("conversational_close_ready")
        )
        binding_execution_allowed = False
        if close_readiness.get("human_takeover_required") is True:
            human_takeover = True
            blockers.append("commercial_human_takeover_required")

    if fatal:
        blockers.append("recall_bot_fatal")
        human_takeover = True

    return RecallMeetingStateSnapshot(
        meeting_id=clean_id,
        avatar_id=avatar_id,
        lifecycle_status=lifecycle_status,
        lifecycle_sub_code=lifecycle_sub_code,
        joined_meeting=joined,
        currently_in_call=current,
        waiting_room=waiting,
        recording_active=recording,
        terminal=terminal,
        fatal=fatal,
        observation_count=observation_count,
        latest_buyer_utterance=latest_buyer,
        recommended_action=recommended_action,
        response_task=response_task,
        close_readiness=close_body,
        conversational_close_ready=conversational_close_ready,
        binding_execution_allowed=binding_execution_allowed,
        human_takeover_required=human_takeover,
        blockers=tuple(sorted(set(blockers))),
    )


def materialize_recall_meeting_state_snapshot(
    *,
    meeting_id: str,
    guidance_root: str | Path,
    runtime_state_root: str | Path,
    output_root: str | Path,
    close_readiness_root: str | Path | None = None,
) -> Path:
    snapshot = build_recall_meeting_state_snapshot(
        meeting_id=meeting_id,
        guidance_root=guidance_root,
        runtime_state_root=runtime_state_root,
        close_readiness_root=close_readiness_root,
    )
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    target = root / f"{snapshot.meeting_id}.json"
    tmp = root / f".{snapshot.meeting_id}.{os.getpid()}.tmp"
    encoded = (json.dumps(snapshot.as_dict(), sort_keys=True, separators=(",", ":")) + "\n").encode()
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
