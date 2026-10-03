"""Non-executing Recall Output Media plan for Digital Avatar COPILOT."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from empire_os.digital_avatar import (
    AvatarMeetingMode,
    AvatarMeetingSession,
    DigitalAvatarIdentity,
)
from empire_os.digital_avatar_presence_token import AvatarPresenceToken


_ALLOWED_REGIONS = {
    "us-west-2",
    "us-east-1",
    "eu-central-1",
    "ap-northeast-1",
}


def _public_https_url(value: str) -> str:
    raw = str(value or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("presence URL must be public HTTPS")
    if (parsed.hostname or "").lower() in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("presence URL cannot be loopback")
    return raw


@dataclass(frozen=True)
class RecallCopilotOutputMediaPlan:
    meeting_id: str
    avatar_id: str
    bot_id: str
    region: str
    presence_url: str
    presence_token_sha256: str
    presence_token_issued_at: int
    presence_token_expires_at: int
    voice_profile_ref: str
    visual_profile_ref: str
    request_body: dict[str, Any]
    mode: str = "COPILOT"
    presence_runtime_audio_locked: bool = True
    per_turn_speech_approval_required: bool = True
    output_media_start_allowed: bool = False
    output_media_start_performed: bool = False
    speech_execution_allowed: bool = False
    commercial_execution_allowed: bool = False
    execution_authority: str = "none"

    @property
    def endpoint(self) -> str:
        return (
            f"https://{self.region}.recall.ai/api/v1/bot/"
            f"{self.bot_id}/output_media/"
        )

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["endpoint"] = self.endpoint
        return data


def build_recall_copilot_output_media_plan(
    *,
    identity: DigitalAvatarIdentity,
    session: AvatarMeetingSession,
    bot_id: str,
    region: str,
    presence_base_url: str,
    presence_token: AvatarPresenceToken,
) -> RecallCopilotOutputMediaPlan:
    identity.validate()
    session.validate()
    if session.mode != AvatarMeetingMode.COPILOT:
        raise ValueError("Recall Output Media plan requires COPILOT mode")
    if session.avatar_id != identity.avatar_id:
        raise ValueError("Output Media avatar/session identity mismatch")
    if session.disclosure_announced is not True:
        raise ValueError("AI disclosure required before Output Media planning")

    clean_bot = str(bot_id or "").strip()
    clean_region = str(region or "").strip()
    if not clean_bot:
        raise ValueError("Recall bot id required")
    if clean_region not in _ALLOWED_REGIONS:
        raise ValueError("unsupported Recall region")

    voice_ref = str(identity.voice_profile_ref or "").strip()
    visual_ref = str(identity.visual_profile_ref or "").strip()
    if not voice_ref:
        raise ValueError("bound avatar voice profile required")
    if not visual_ref:
        raise ValueError("bound avatar visual profile required")

    claims = presence_token.claims
    if claims.meeting_id != session.meeting_id:
        raise ValueError("presence token meeting mismatch")
    if claims.avatar_id != identity.avatar_id:
        raise ValueError("presence token avatar mismatch")
    if claims.bot_id != clean_bot:
        raise ValueError("presence token bot mismatch")
    if claims.mode != "copilot":
        raise ValueError("presence token mode mismatch")

    base = _public_https_url(presence_base_url)
    parsed = urlparse(base)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if "token" in query:
        raise ValueError("presence base URL must not contain token query")
    query["token"] = presence_token.token
    presence_url = urlunparse(
        parsed._replace(query=urlencode(query))
    )

    request_body = {
        "camera": {
            "kind": "webpage",
            "config": {"url": presence_url},
        }
    }
    return RecallCopilotOutputMediaPlan(
        meeting_id=session.meeting_id,
        avatar_id=identity.avatar_id,
        bot_id=clean_bot,
        region=clean_region,
        presence_url=presence_url,
        presence_token_sha256=presence_token.token_sha256,
        presence_token_issued_at=claims.issued_at,
        presence_token_expires_at=claims.expires_at,
        voice_profile_ref=voice_ref,
        visual_profile_ref=visual_ref,
        request_body=request_body,
    )
