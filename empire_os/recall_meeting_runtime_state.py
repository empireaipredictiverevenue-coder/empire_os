"""Aggregate verified Recall lifecycle records into one meeting runtime state."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class RecallMeetingRuntimeState:
    meeting_id: str
    avatar_id: str
    bot_id: str
    status_code: str
    sub_code: str | None
    updated_at: str
    event_count: int
    waiting_room: bool
    joined_meeting: bool
    currently_in_call: bool
    recording_active: bool
    terminal: bool
    fatal: bool
    evidence_refs: tuple[str, ...]
    truth_class: str = "VERIFIED"
    polling_performed: bool = False
    speech_execution: bool = False
    commercial_execution: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _time(value: str) -> datetime:
    raw = str(value or "").strip()
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("Recall lifecycle updated_at must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("Recall lifecycle updated_at must include timezone")
    return parsed.astimezone(timezone.utc)


def build_recall_meeting_runtime_state(
    records: Iterable[Mapping[str, Any]],
    *,
    meeting_id: str,
) -> RecallMeetingRuntimeState | None:
    clean_meeting = str(meeting_id or "").strip()
    if not clean_meeting:
        raise ValueError("meeting_id required")

    matched: list[tuple[datetime, Mapping[str, Any], Mapping[str, Any]]] = []
    for record in records:
        lifecycle = record.get("lifecycle")
        if not isinstance(lifecycle, Mapping):
            continue
        binding = lifecycle.get("binding")
        if not isinstance(binding, Mapping):
            continue
        if str(binding.get("meeting_id") or "").strip() != clean_meeting:
            continue
        if record.get("truth_class") != "VERIFIED":
            raise ValueError("Recall lifecycle record must be VERIFIED")
        if str(record.get("execution_authority") or "").lower() != "none":
            raise ValueError("Recall lifecycle record grants forbidden authority")
        matched.append((_time(str(lifecycle.get("updated_at") or "")), record, lifecycle))

    if not matched:
        return None

    matched.sort(key=lambda row: row[0])
    _, latest_record, latest = matched[-1]
    binding = latest["binding"]
    status_code = str(latest.get("status_code") or "").strip()
    bot_id = str(latest.get("bot_id") or "").strip()
    avatar_id = str(binding.get("avatar_id") or "").strip()
    if not status_code or not bot_id or not avatar_id:
        raise ValueError("Recall lifecycle state identity incomplete")


    evidence_refs: list[str] = []
    for _, record, _lifecycle in matched:
        verification = record.get("source_verification")
        if not isinstance(verification, Mapping):
            continue
        webhook_id = str(verification.get("webhook_id") or "").strip()
        timestamp = str(verification.get("webhook_timestamp") or "").strip()
        payload_sha = str(verification.get("payload_sha256") or "").strip()
        if webhook_id and timestamp and payload_sha:
            evidence_refs.append(
                f"recall-verification:{webhook_id}:{timestamp}:{payload_sha[:24]}"
            )

    return RecallMeetingRuntimeState(
        meeting_id=clean_meeting,
        avatar_id=avatar_id,
        bot_id=bot_id,
        status_code=status_code,
        sub_code=(str(latest.get("sub_code") or "").strip() or None),
        updated_at=str(latest.get("updated_at") or "").strip(),
        event_count=len(matched),
        waiting_room=status_code == "in_waiting_room",
        joined_meeting=bool(latest.get("joined_meeting")),
        currently_in_call=status_code in {
            "in_call_not_recording",
            "recording_permission_allowed",
            "recording_permission_denied",
            "in_call_recording",
        },
        recording_active=bool(latest.get("recording_active")),
        terminal=bool(latest.get("terminal")),
        fatal=bool(latest.get("fatal")),
        evidence_refs=tuple(dict.fromkeys(evidence_refs)),
    )


def refresh_recall_meeting_runtime_state(
    *,
    lifecycle_root: str | Path,
    meeting_id: str,
    output_path: str | Path,
) -> RecallMeetingRuntimeState | None:
    records: list[Mapping[str, Any]] = []
    root = Path(lifecycle_root)
    if root.is_dir():
        for path in sorted(root.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError("Recall lifecycle record unreadable") from exc
            if isinstance(payload, Mapping):
                records.append(payload)

    state = build_recall_meeting_runtime_state(
        records,
        meeting_id=meeting_id,
    )
    if state is None:
        return None

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(target.parent, 0o700)
    tmp = target.parent / f".{target.name}.{os.getpid()}.tmp"
    encoded = (
        json.dumps(state.as_dict(), sort_keys=True, separators=(",", ":"))
        + "\n"
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
    return state
