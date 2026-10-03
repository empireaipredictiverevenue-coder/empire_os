"""Async verified Recall spool -> observed meeting record worker."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from typing import Any, Mapping

from empire_os.meeting_gateway import MeetingObservation, MeetingPlatform
from empire_os.recall_bot_binding import extract_recall_bot_binding
from empire_os.recall_meeting_adapter import normalize_verified_recall_event
from empire_os.recall_verified_spool import decode_verified_spool_record


@dataclass(frozen=True)
class RoutedRecallObservation:
    queue_id: str
    meeting_id: str
    avatar_id: str
    platform: MeetingPlatform
    verification_ref: str
    observation: MeetingObservation
    truth_class: str = "OBSERVED"
    canonical_truth_written: bool = False
    inference_performed: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["platform"] = self.platform.value
        data["observation"] = self.observation.as_dict()
        return data


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} mapping required")
    return value


def route_verified_spool_record(
    record: Mapping[str, Any],
) -> RoutedRecallObservation:
    decoded = decode_verified_spool_record(record)
    queue_id = decoded.queue_id
    payload = decoded.payload

    try:
        binding = extract_recall_bot_binding(
            payload,
            require_shadow=True,
        )
    except ValueError as exc:
        if "execution authority" in str(exc):
            raise ValueError(
                "Recall event metadata grants forbidden authority"
            ) from exc
        raise

    meeting_id = binding.meeting_id
    avatar_id = binding.avatar_id
    platform = binding.platform

    observation = normalize_verified_recall_event(
        meeting_id=meeting_id,
        platform=platform,
        payload=payload,
        received_at=decoded.received_at,
        verified=True,
        participant_roles={},
    )
    return RoutedRecallObservation(
        queue_id=queue_id,
        meeting_id=meeting_id,
        avatar_id=avatar_id,
        platform=platform,
        verification_ref=decoded.verification_ref,
        observation=observation,
    )


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    tmp = path.parent / f".{path.name}.{os.getpid()}.tmp"
    encoded = (
        json.dumps(payload, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        os.chmod(path, 0o600)
    finally:
        if tmp.exists():
            tmp.unlink()


def process_verified_spool(
    *,
    spool_root: str | Path,
    observation_root: str | Path,
    max_items: int = 100,
) -> dict[str, Any]:
    source_root = Path(spool_root)
    target_root = Path(observation_root)
    processed = 0
    failed = 0
    duplicates = 0
    changed_meetings: set[str] = set()

    if not source_root.is_dir():
        return {
            "processed": 0,
            "failed": 0,
            "duplicates": 0,
            "meetings": [],
            "execution_authority": "none",
        }

    for source in sorted(source_root.glob("*.json"))[: max(0, int(max_items))]:
        try:
            record = json.loads(source.read_text(encoding="utf-8"))
            routed = route_verified_spool_record(record)
            target = target_root / f"{routed.queue_id}.json"
            if target.exists():
                duplicates += 1
            else:
                _atomic_json(target, routed.as_dict())
                processed += 1
                changed_meetings.add(routed.meeting_id)
            source.unlink()
        except Exception:
            failed += 1

    return {
        "processed": processed,
        "failed": failed,
        "duplicates": duplicates,
        "meetings": sorted(changed_meetings),
        "canonical_truth_written": False,
        "execution_authority": "none",
    }
