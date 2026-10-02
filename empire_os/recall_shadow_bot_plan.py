"""Non-executing Recall.ai shadow bot plan for Empire Digital Avatar."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from empire_os.meeting_gateway import MeetingPlatform


_REALTIME_EVENTS = (
    "transcript.data",
    "participant_events.join",
    "participant_events.leave",
    "participant_events.chat_message",
    "participant_events.screenshare_on",
    "participant_events.screenshare_off",
)


def _https_url(value: str, name: str) -> str:
    raw = str(value or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"{name} must be a public HTTPS URL")
    if parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError(f"{name} cannot be localhost")
    return raw


def _iso(value: str) -> str:
    raw = str(value or "").strip()
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("join_at must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("join_at must include timezone")
    return raw


@dataclass(frozen=True)
class RecallShadowBotPlan:
    meeting_id: str
    avatar_id: str
    platform: MeetingPlatform
    bot_name: str
    meeting_url: str
    realtime_webhook_url: str
    request_body: dict[str, Any]
    recording_consent_evidence_ref: str
    webhook_verification_evidence_ref: str
    mode: str = "SHADOW"
    api_call_allowed: bool = False
    live_join_execution: bool = False
    output_media_enabled: bool = False
    chat_send_enabled: bool = False
    speech_execution: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["platform"] = self.platform.value
        return data


def build_recall_shadow_bot_plan(
    *,
    meeting_id: str,
    avatar_id: str,
    platform: MeetingPlatform,
    bot_name: str,
    meeting_url: str,
    realtime_webhook_url: str,
    recording_consent_evidence_ref: str,
    webhook_verification_evidence_ref: str,
    join_at: str | None = None,
) -> RecallShadowBotPlan:
    clean_meeting = str(meeting_id or "").strip()
    clean_avatar = str(avatar_id or "").strip()
    clean_name = str(bot_name or "").strip()
    if not clean_meeting or not clean_avatar or not clean_name:
        raise ValueError("meeting_id, avatar_id and bot_name required")
    try:
        resolved_platform = (
            platform
            if isinstance(platform, MeetingPlatform)
            else MeetingPlatform(str(platform))
        )
    except ValueError as exc:
        raise ValueError("unsupported meeting platform") from exc
    if len(clean_name) > 100:
        raise ValueError("bot_name exceeds Recall limit")
    if "ai" not in clean_name.lower():
        raise ValueError("bot_name must visibly identify the AI representative")

    meeting = _https_url(meeting_url, "meeting_url")
    webhook = _https_url(realtime_webhook_url, "realtime_webhook_url")
    consent_ref = str(recording_consent_evidence_ref or "").strip()
    verify_ref = str(webhook_verification_evidence_ref or "").strip()
    if not consent_ref:
        raise ValueError("recording consent evidence required")
    if not verify_ref:
        raise ValueError("webhook verification evidence required")

    request_body: dict[str, Any] = {
        "meeting_url": meeting,
        "bot_name": clean_name,
        "metadata": {
            "empire_meeting_id": clean_meeting,
            "empire_avatar_id": clean_avatar,
            "empire_platform": resolved_platform.value,
            "empire_mode": "shadow",
            "execution_authority": "none",
        },
        "recording_config": {
            "transcript": {
                "provider": {
                    "recallai_streaming": {
                        "mode": "prioritize_low_latency",
                        "language_code": "en",
                    }
                },
                "diarization": {
                    "use_separate_streams_when_available": True,
                },
            },
            "realtime_endpoints": [{
                "type": "webhook",
                "url": webhook,
                "events": list(_REALTIME_EVENTS),
            }],
        },
    }


    if join_at is not None:
        request_body["join_at"] = _iso(join_at)

    return RecallShadowBotPlan(
        meeting_id=clean_meeting,
        avatar_id=clean_avatar,
        platform=resolved_platform,
        bot_name=clean_name,
        meeting_url=meeting,
        realtime_webhook_url=webhook,
        request_body=request_body,
        recording_consent_evidence_ref=consent_ref,
        webhook_verification_evidence_ref=verify_ref,
    )
