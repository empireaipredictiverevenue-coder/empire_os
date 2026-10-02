"""Provider-neutral meeting observation foundation for Digital Avatar."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Iterable

from empire_os.digital_avatar import AvatarMeetingMode, AvatarMeetingSession


class MeetingPlatform(str, Enum):
    ZOOM = "zoom"
    GOOGLE_MEET = "google_meet"
    MICROSOFT_TEAMS = "microsoft_teams"
    WEBEX = "webex"
    GENERIC = "generic"


class MeetingObservationKind(str, Enum):
    TRANSCRIPT_TURN = "transcript_turn"
    CHAT_MESSAGE = "chat_message"
    PARTICIPANT_JOINED = "participant_joined"
    PARTICIPANT_LEFT = "participant_left"
    SCREEN_SHARE_STARTED = "screen_share_started"
    SCREEN_SHARE_ENDED = "screen_share_ended"


class MeetingSpeakerRole(str, Enum):
    BUYER = "buyer"
    AVATAR_OWNER = "avatar_owner"
    AVATAR = "avatar"
    INTERNAL = "internal"
    UNKNOWN = "unknown"


def _iso(value: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("occurred_at required")
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("occurred_at must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("occurred_at must include timezone")
    return parsed


@dataclass(frozen=True)
class MeetingObservation:
    meeting_id: str
    external_meeting_id: str
    platform: MeetingPlatform
    provider_event_id: str
    kind: MeetingObservationKind
    occurred_at: str
    evidence_ref: str
    speaker_ref: str | None = None
    speaker_name: str | None = None
    speaker_role: MeetingSpeakerRole = MeetingSpeakerRole.UNKNOWN
    text: str | None = None
    is_final: bool = True

    def validate(self) -> None:
        for name, value in (
            ("meeting_id", self.meeting_id),
            ("external_meeting_id", self.external_meeting_id),
            ("provider_event_id", self.provider_event_id),
            ("evidence_ref", self.evidence_ref),
        ):
            if not str(value or "").strip():
                raise ValueError(f"{name} required")
        _iso(self.occurred_at)
        if self.kind in {
            MeetingObservationKind.TRANSCRIPT_TURN,
            MeetingObservationKind.CHAT_MESSAGE,
        }:
            if not str(self.speaker_ref or "").strip():
                raise ValueError("speaker_ref required for textual meeting events")
            if not str(self.text or "").strip():
                raise ValueError("text required for textual meeting events")

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["platform"] = self.platform.value
        data["kind"] = self.kind.value
        data["speaker_role"] = self.speaker_role.value
        return data


    def fingerprint(self) -> str:
        payload = json.dumps(
            self.as_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return sha256(payload).hexdigest()


@dataclass(frozen=True)
class ShadowMeetingState:
    meeting_id: str
    avatar_id: str
    platform: MeetingPlatform
    observation_count: int
    transcript_turn_count: int
    latest_buyer_utterance: MappingLike | None
    observations: tuple[dict[str, Any], ...]
    mode: str = "OBSERVE"
    private_guidance_only: bool = True
    speech_execution: bool = False
    meeting_action_execution: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


MappingLike = dict[str, Any]


def build_shadow_meeting_state(
    *,
    session: AvatarMeetingSession,
    observations: Iterable[MeetingObservation],
) -> ShadowMeetingState:
    session.validate()
    if session.mode != AvatarMeetingMode.SHADOW:
        raise ValueError("shadow meeting state requires SHADOW mode")

    by_event: dict[str, MeetingObservation] = {}
    for observation in observations:
        observation.validate()
        if observation.meeting_id != session.meeting_id:
            raise ValueError("meeting observation/session identity mismatch")
        prior = by_event.get(observation.provider_event_id)
        if prior is not None:
            if prior.fingerprint() != observation.fingerprint():
                raise ValueError("conflicting provider_event_id reuse")
            continue
        by_event[observation.provider_event_id] = observation

    ordered = sorted(
        by_event.values(),
        key=lambda item: (_iso(item.occurred_at), item.provider_event_id),
    )
    platforms = {item.platform for item in ordered}
    if len(platforms) > 1:
        raise ValueError("meeting observations cannot mix platforms")
    platform = (
        next(iter(platforms))
        if platforms
        else MeetingPlatform.GENERIC
    )


    transcript_turns = [
        item
        for item in ordered
        if item.kind == MeetingObservationKind.TRANSCRIPT_TURN
        and item.is_final
    ]
    buyer_turns = [
        item
        for item in transcript_turns
        if item.speaker_role == MeetingSpeakerRole.BUYER
    ]
    latest_buyer = buyer_turns[-1].as_dict() if buyer_turns else None

    return ShadowMeetingState(
        meeting_id=session.meeting_id,
        avatar_id=session.avatar_id,
        platform=platform,
        observation_count=len(ordered),
        transcript_turn_count=len(transcript_turns),
        latest_buyer_utterance=latest_buyer,
        observations=tuple(item.as_dict() for item in ordered),
    )
