"""Async verified Recall spool -> observed meeting record worker."""
from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Mapping

from empire_os.meeting_gateway import MeetingObservation, MeetingPlatform
from empire_os.recall_meeting_adapter import normalize_verified_recall_event


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
    if record.get("schema_version") != "empire.recall_verified_spool.v1":
        raise ValueError("unsupported Recall spool schema")

    queue_id = str(record.get("queue_id") or "").strip()
    verification = _mapping(record.get("verification"), "verification")
    if verification.get("verified") is not True:
        raise ValueError("spool verification evidence missing")
    payload_sha = str(verification.get("payload_sha256") or "").strip()
    webhook_id = str(verification.get("webhook_id") or "").strip()
    timestamp = str(verification.get("webhook_timestamp") or "").strip()
    if not queue_id or not payload_sha or not webhook_id or not timestamp:
        raise ValueError("spool verification identity incomplete")

    encoded = str(record.get("raw_payload_base64") or "").strip()
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError("spool payload encoding invalid") from exc
    if sha256(raw).hexdigest() != payload_sha:
        raise ValueError("spool payload hash mismatch")

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("spool payload is not valid JSON") from exc
    payload = _mapping(payload, "Recall payload")


    envelope = _mapping(payload.get("data"), "Recall data")
    bot = _mapping(envelope.get("bot"), "Recall bot")
    metadata = _mapping(bot.get("metadata"), "Recall bot metadata")

    meeting_id = str(metadata.get("empire_meeting_id") or "").strip()
    avatar_id = str(metadata.get("empire_avatar_id") or "").strip()
    if not meeting_id or not avatar_id:
        raise ValueError("Empire meeting/avatar correlation missing")
    if str(metadata.get("empire_mode") or "").strip().lower() != "shadow":
        raise ValueError("Recall event is not bound to SHADOW mode")
    if str(metadata.get("execution_authority") or "").strip().lower() != "none":
        raise ValueError("Recall event metadata grants forbidden authority")
    try:
        platform = MeetingPlatform(
            str(metadata.get("empire_platform") or "").strip()
        )
    except ValueError as exc:
        raise ValueError("Empire meeting platform correlation invalid") from exc

    received_at = str(record.get("received_at") or "").strip()
    observation = normalize_verified_recall_event(
        meeting_id=meeting_id,
        platform=platform,
        payload=payload,
        received_at=received_at,
        verified=True,
        participant_roles={},
    )
    verification_ref = (
        f"recall-verification:{webhook_id}:{timestamp}:{payload_sha[:24]}"
    )


    return RoutedRecallObservation(
        queue_id=queue_id,
        meeting_id=meeting_id,
        avatar_id=avatar_id,
        platform=platform,
        verification_ref=verification_ref,
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
