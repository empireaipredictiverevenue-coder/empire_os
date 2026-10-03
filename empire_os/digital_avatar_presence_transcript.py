"""Low-latency, session-authenticated transcript observations from Recall Output Media."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Mapping

from empire_os.digital_avatar_presence_token import AvatarPresenceClaims


@dataclass(frozen=True)
class PresenceTranscriptObservation:
    observation_id: str
    meeting_id: str
    avatar_id: str
    bot_id: str
    participant_ref: str | None
    participant_name: str | None
    text: str
    received_at: str
    is_final: bool
    source: str = "recall_output_media_transcript_ws"
    truth_class: str = "SESSION_OBSERVED"
    canonical_evidence: bool = False
    commercial_truth_allowed: bool = False
    speech_execution_allowed: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} mapping required")
    return value


def normalize_presence_transcript(
    *,
    claims: AvatarPresenceClaims,
    payload: Mapping[str, Any],
    received_at: str,
) -> PresenceTranscriptObservation:
    if claims.mode != "copilot":
        raise ValueError("presence transcript requires COPILOT session")
    body = _mapping(payload, "presence transcript payload")
    transcript_value = body.get("transcript")
    transcript = (
        _mapping(transcript_value, "presence transcript")
        if transcript_value is not None
        else body
    )
    words = transcript.get("words")
    if not isinstance(words, list):
        raise ValueError("presence transcript words list required")
    pieces = [
        str(word.get("text") or "").strip()
        for word in words
        if isinstance(word, Mapping) and str(word.get("text") or "").strip()
    ]
    text = " ".join(pieces).strip()
    if not text:
        raise ValueError("presence transcript text required")

    participant_value = transcript.get("participant")
    participant = (
        _mapping(participant_value, "presence participant")
        if participant_value is not None
        else {}
    )
    participant_id = participant.get("id")
    participant_ref = (
        f"recall-participant:{participant_id}"
        if participant_id is not None
        else None
    )
    participant_name = str(participant.get("name") or "").strip() or None

    stable = {
        "meeting_id": claims.meeting_id,
        "avatar_id": claims.avatar_id,
        "bot_id": claims.bot_id,
        "participant_id": participant_id,
        "text": text,
        "received_at": str(received_at or "").strip(),
    }
    digest = sha256(
        json.dumps(
            stable,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    return PresenceTranscriptObservation(
        observation_id=f"presence-transcript:{digest}",
        meeting_id=claims.meeting_id,
        avatar_id=claims.avatar_id,
        bot_id=claims.bot_id,
        participant_ref=participant_ref,
        participant_name=participant_name,
        text=text,
        received_at=str(received_at or "").strip(),
        is_final=bool(transcript.get("is_final", True)),
    )
