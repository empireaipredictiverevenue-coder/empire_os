"""Convert verified Recall spool records into observed meeting records."""
from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.meeting_gateway import MeetingSpeakerRole
from empire_os.recall_bot_binding import extract_recall_bot_binding
from empire_os.recall_meeting_adapter import normalize_verified_recall_event


@dataclass(frozen=True)
class RecallObservedRecord:
    queue_id: str
    avatar_id: str
    binding_truth_class: str
    observation: Mapping[str, Any]
    source_payload_sha256: str
    source_verification: Mapping[str, Any]
    truth_class: str = "OBSERVED"
    inference_performed: bool = False
    commercial_truth_written: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load_spool_record(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("invalid Recall spool record") from exc
    if not isinstance(payload, dict):
        raise ValueError("Recall spool record must be a JSON object")
    if payload.get("schema_version") != "empire.recall_verified_spool.v1":
        raise ValueError("unsupported Recall spool schema")
    return payload


def build_observed_record_from_spool(
    *,
    spool_path: str | Path,
    participant_roles: Mapping[str, MeetingSpeakerRole | str] | None = None,
    received_at_fallback: str = "",
) -> RecallObservedRecord:
    record = _load_spool_record(spool_path)
    verification = record.get("verification")
    if not isinstance(verification, Mapping) or verification.get("verified") is not True:
        raise ValueError("spool verification evidence missing")

    encoded = str(record.get("raw_payload_base64") or "")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError("invalid Recall spool payload encoding") from exc

    actual_hash = sha256(raw).hexdigest()
    expected_hash = str(verification.get("payload_sha256") or "")
    if actual_hash != expected_hash:
        raise ValueError("Recall spool payload hash mismatch")


    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("verified Recall spool payload is not valid JSON") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("verified Recall spool payload must be a JSON object")

    binding = extract_recall_bot_binding(payload)
    observation = normalize_verified_recall_event(
        meeting_id=binding.meeting_id,
        platform=binding.platform,
        payload=payload,
        received_at=str(record.get("received_at") or received_at_fallback),
        verified=True,
        participant_roles=participant_roles or {},
    )
    queue_id = str(record.get("queue_id") or "").strip()
    if not queue_id:
        raise ValueError("Recall spool queue_id required")

    return RecallObservedRecord(
        queue_id=queue_id,
        avatar_id=binding.avatar_id,
        binding_truth_class=binding.truth_class,
        observation=observation.as_dict(),
        source_payload_sha256=actual_hash,
        source_verification=dict(verification),
    )


def materialize_observed_record(
    *,
    spool_path: str | Path,
    output_root: str | Path,
    participant_roles: Mapping[str, MeetingSpeakerRole | str] | None = None,
) -> Path:
    observed = build_observed_record_from_spool(
        spool_path=spool_path,
        participant_roles=participant_roles,
    )
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = root / f"{observed.queue_id}.json"
    if target.exists():
        return target

    tmp = root / f".{observed.queue_id}.tmp"
    tmp.write_text(
        json.dumps(observed.as_dict(), sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
    )
    tmp.chmod(0o600)
    tmp.replace(target)
    target.chmod(0o600)
    return target
