"""Canonical verified Recall webhook ingress for Digital Avatar."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any, Mapping

from empire_os.meeting_gateway import (
    MeetingObservation,
    MeetingPlatform,
    MeetingSpeakerRole,
)
from empire_os.recall_bot_binding import (
    RecallBotBinding,
    extract_recall_bot_binding,
)
from empire_os.recall_meeting_adapter import normalize_verified_recall_event
from empire_os.recall_webhook_verification import (
    RecallVerificationEvidence,
    verify_recall_request,
)


@dataclass(frozen=True)
class VerifiedRecallIngressResult:
    verification: RecallVerificationEvidence
    observation: MeetingObservation
    raw_payload_sha256: str
    processing_order: tuple[str, ...] = (
        "verify_signature",
        "parse_json",
        "normalize_event",
    )
    persistence_performed: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "verification": self.verification.as_dict(),
            "observation": self.observation.as_dict(),
        }


def verify_and_normalize_recall_event(
    *,
    secret: str,
    headers: Mapping[str, Any],
    raw_payload: bytes | str,
    meeting_id: str,
    platform: MeetingPlatform,
    received_at: str,
    participant_roles: Mapping[str, MeetingSpeakerRole | str] | None = None,
) -> VerifiedRecallIngressResult:
    verification = verify_recall_request(
        secret=secret,
        headers=headers,
        raw_payload=raw_payload,
    )


    raw_bytes = (
        raw_payload
        if isinstance(raw_payload, bytes)
        else str(raw_payload).encode("utf-8")
    )
    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("verified Recall payload is not valid JSON") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("verified Recall payload must be a JSON object")

    observation = normalize_verified_recall_event(
        meeting_id=meeting_id,
        platform=platform,
        payload=payload,
        received_at=received_at,
        verified=True,
        participant_roles=participant_roles or {},
    )
    return VerifiedRecallIngressResult(
        verification=verification,
        observation=observation,
        raw_payload_sha256=verification.payload_sha256,
    )


@dataclass(frozen=True)
class BoundVerifiedRecallIngressResult:
    verification: RecallVerificationEvidence
    binding: RecallBotBinding
    observation: MeetingObservation
    raw_payload_sha256: str
    processing_order: tuple[str, ...] = (
        "verify_signature",
        "parse_json",
        "bind_signed_bot_metadata",
        "normalize_event",
    )
    persistence_performed: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "verification": self.verification.as_dict(),
            "binding": self.binding.as_dict(),
            "observation": self.observation.as_dict(),
        }


def verify_bind_and_normalize_recall_event(
    *,
    secret: str,
    headers: Mapping[str, Any],
    raw_payload: bytes | str,
    received_at: str,
    participant_roles: Mapping[str, MeetingSpeakerRole | str] | None = None,
) -> BoundVerifiedRecallIngressResult:
    verification = verify_recall_request(
        secret=secret,
        headers=headers,
        raw_payload=raw_payload,
    )

    raw_bytes = (
        raw_payload
        if isinstance(raw_payload, bytes)
        else str(raw_payload).encode("utf-8")
    )
    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("verified Recall payload is not valid JSON") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("verified Recall payload must be a JSON object")


    binding = extract_recall_bot_binding(payload)
    observation = normalize_verified_recall_event(
        meeting_id=binding.meeting_id,
        platform=binding.platform,
        payload=payload,
        received_at=received_at,
        verified=True,
        participant_roles=participant_roles or {},
    )
    if observation.external_meeting_id != binding.bot_id:
        raise ValueError("Recall observation/binding bot mismatch")

    return BoundVerifiedRecallIngressResult(
        verification=verification,
        binding=binding,
        observation=observation,
        raw_payload_sha256=verification.payload_sha256,
    )
