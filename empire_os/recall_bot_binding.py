"""Extract Empire Digital Avatar binding from signed Recall bot metadata."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from empire_os.meeting_gateway import MeetingPlatform


@dataclass(frozen=True)
class RecallBotBinding:
    bot_id: str
    meeting_id: str
    avatar_id: str
    platform: MeetingPlatform
    mode: str
    execution_authority: str
    truth_class: str = "VERIFIED"

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["platform"] = self.platform.value
        return data


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} mapping required")
    return value


def _text(value: Any) -> str:
    return str(value or "").strip()


def extract_recall_bot_binding(
    payload: Mapping[str, Any],
    *,
    require_shadow: bool = True,
) -> RecallBotBinding:
    envelope = _mapping(payload.get("data"), "Recall data")
    bot = _mapping(envelope.get("bot"), "Recall bot")
    bot_id = _text(bot.get("id"))
    if not bot_id:
        raise ValueError("Recall bot id required")

    metadata = _mapping(bot.get("metadata"), "Recall bot metadata")
    meeting_id = _text(metadata.get("empire_meeting_id"))
    avatar_id = _text(metadata.get("empire_avatar_id"))
    platform_raw = _text(metadata.get("empire_platform"))
    mode = _text(metadata.get("empire_mode")).lower()
    execution_authority = _text(
        metadata.get("execution_authority")
    ).lower()

    if not meeting_id or not avatar_id:
        raise ValueError("Empire meeting/avatar binding missing from Recall metadata")
    try:
        platform = MeetingPlatform(platform_raw)
    except ValueError as exc:
        raise ValueError("unsupported Empire meeting platform in Recall metadata") from exc

    if require_shadow and mode != "shadow":
        raise ValueError("Recall bot metadata is not SHADOW mode")
    if execution_authority != "none":
        raise ValueError("Recall bot metadata must have no execution authority")

    return RecallBotBinding(
        bot_id=bot_id,
        meeting_id=meeting_id,
        avatar_id=avatar_id,
        platform=platform,
        mode=mode,
        execution_authority=execution_authority,
    )
