"""Pure normalizer for verified Recall.ai real-time meeting events."""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping

from empire_os.meeting_gateway import (
    MeetingObservation,
    MeetingObservationKind,
    MeetingPlatform,
    MeetingSpeakerRole,
)


_EVENT_KINDS = {
    "transcript.data": (MeetingObservationKind.TRANSCRIPT_TURN, True),
    "transcript.partial_data": (MeetingObservationKind.TRANSCRIPT_TURN, False),
    "participant_events.chat_message": (MeetingObservationKind.CHAT_MESSAGE, True),
    "participant_events.join": (MeetingObservationKind.PARTICIPANT_JOINED, True),
    "participant_events.leave": (MeetingObservationKind.PARTICIPANT_LEFT, True),
    "participant_events.screenshare_on": (
        MeetingObservationKind.SCREEN_SHARE_STARTED,
        True,
    ),
    "participant_events.screenshare_off": (
        MeetingObservationKind.SCREEN_SHARE_ENDED,
        True,
    ),
}


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} mapping required")
    return value


def _text(value: Any) -> str:
    return str(value or "").strip()


def _stable_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _speaker_role(
    participant_id: Any,
    roles: Mapping[str, MeetingSpeakerRole | str],
) -> MeetingSpeakerRole:
    value = roles.get(str(participant_id))
    if isinstance(value, MeetingSpeakerRole):
        return value
    if value is None:
        return MeetingSpeakerRole.UNKNOWN
    try:
        return MeetingSpeakerRole(str(value))
    except ValueError as exc:
        raise ValueError("invalid explicit participant role") from exc


def _participant(event_data: Mapping[str, Any]) -> Mapping[str, Any]:
    participant = event_data.get("participant")
    return _mapping(participant, "participant") if participant is not None else {}


def _event_time(
    event_name: str,
    event_data: Mapping[str, Any],
    received_at: str,
) -> str:
    if event_name.startswith("participant_events."):
        stamp = event_data.get("timestamp")
        stamp = _mapping(stamp, "participant timestamp")
        absolute = _text(stamp.get("absolute"))
        if absolute:
            return absolute
    return _text(received_at)


def normalize_verified_recall_event(
    *,
    meeting_id: str,
    platform: MeetingPlatform,
    payload: Mapping[str, Any],
    received_at: str,
    verified: bool,
    participant_roles: Mapping[str, MeetingSpeakerRole | str] | None = None,
) -> MeetingObservation:
    if verified is not True:
        raise ValueError("unverified Recall event rejected")
    if not _text(meeting_id):
        raise ValueError("canonical meeting_id required")

    event_name = _text(payload.get("event"))
    if event_name not in _EVENT_KINDS:
        raise ValueError("unsupported Recall real-time event")
    kind, is_final = _EVENT_KINDS[event_name]

    envelope = _mapping(payload.get("data"), "Recall data")
    event_data = _mapping(envelope.get("data"), "Recall event data")
    bot = _mapping(envelope.get("bot"), "Recall bot")
    bot_id = _text(bot.get("id"))
    if not bot_id:
        raise ValueError("Recall bot id required")

    participant = _participant(event_data)
    participant_id = participant.get("id")
    speaker_ref = (
        f"recall-participant:{participant_id}"
        if participant_id is not None
        else None
    )
    speaker_name = _text(participant.get("name")) or None
    role = _speaker_role(participant_id, participant_roles or {})


    text = None
    artifact_id = ""
    if event_name.startswith("transcript."):
        words = event_data.get("words")
        if not isinstance(words, list):
            raise ValueError("Recall transcript words list required")
        pieces = [
            _text(word.get("text"))
            for word in words
            if isinstance(word, Mapping) and _text(word.get("text"))
        ]
        text = " ".join(pieces).strip()
        transcript = _mapping(envelope.get("transcript"), "Recall transcript")
        artifact_id = _text(transcript.get("id"))
        if not artifact_id:
            raise ValueError("Recall transcript id required")
    elif event_name == "participant_events.chat_message":
        nested = _mapping(event_data.get("data"), "Recall chat data")
        text = _text(nested.get("text"))
        participant_events = _mapping(
            envelope.get("participant_events"),
            "Recall participant events",
        )
        artifact_id = _text(participant_events.get("id"))
    else:
        participant_events = _mapping(
            envelope.get("participant_events"),
            "Recall participant events",
        )
        artifact_id = _text(participant_events.get("id"))

    digest = _stable_hash(payload)
    evidence_ref = (
        f"recall:{bot_id}:{artifact_id or 'realtime'}:{digest[:24]}"
    )


    observation = MeetingObservation(
        meeting_id=_text(meeting_id),
        external_meeting_id=bot_id,
        platform=platform,
        provider_event_id=f"recall:{digest[:32]}",
        kind=kind,
        occurred_at=_event_time(event_name, event_data, received_at),
        evidence_ref=evidence_ref,
        speaker_ref=speaker_ref,
        speaker_name=speaker_name,
        speaker_role=role,
        text=text,
        is_final=is_final,
    )
    observation.validate()
    return observation
