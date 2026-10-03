"""Verified Recall bot lifecycle evidence for Digital Avatar meetings."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from empire_os.recall_bot_binding import (
    RecallBotBinding,
    extract_recall_bot_binding,
)


@dataclass(frozen=True)
class RecallBotLifecycleEvent:
    event: str
    bot_id: str
    status_code: str
    sub_code: str | None
    updated_at: str
    binding: RecallBotBinding
    joined_meeting: bool
    recording_active: bool
    terminal: bool
    fatal: bool
    truth_class: str = "VERIFIED"
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["binding"] = self.binding.as_dict()
        return data


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} mapping required")
    return value


def _text(value: Any) -> str:
    return str(value or "").strip()


def normalize_verified_recall_lifecycle(
    *,
    payload: Mapping[str, Any],
    verified: bool,
) -> RecallBotLifecycleEvent:
    if verified is not True:
        raise ValueError("unverified Recall lifecycle event rejected")

    event = _text(payload.get("event"))
    if not event.startswith("bot."):
        raise ValueError("unsupported Recall bot lifecycle event")

    envelope = _mapping(payload.get("data"), "Recall lifecycle data")
    status = _mapping(envelope.get("data"), "Recall lifecycle status")
    code = _text(status.get("code"))
    updated_at = _text(status.get("updated_at"))
    if not code or not updated_at:
        raise ValueError("Recall lifecycle status code and updated_at required")

    binding = extract_recall_bot_binding(payload)
    sub_code = _text(status.get("sub_code")) or None
    joined = code in {
        "in_call_not_recording",
        "recording_permission_allowed",
        "recording_permission_denied",
        "in_call_recording",
        "call_ended",
        "done",
    }
    recording = code == "in_call_recording"
    terminal = code in {"done", "fatal", "media_expired"}
    fatal = code == "fatal"

    return RecallBotLifecycleEvent(
        event=event,
        bot_id=binding.bot_id,
        status_code=code,
        sub_code=sub_code,
        updated_at=updated_at,
        binding=binding,
        joined_meeting=joined,
        recording_active=recording,
        terminal=terminal,
        fatal=fatal,
    )
