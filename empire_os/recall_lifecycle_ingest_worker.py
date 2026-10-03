"""Verified Recall lifecycle spool -> private bot-state evidence."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Mapping

from empire_os.recall_bot_lifecycle import (
    RecallBotLifecycleEvent,
    normalize_verified_recall_lifecycle,
)
from empire_os.recall_verified_spool import decode_verified_spool_record


@dataclass(frozen=True)
class RoutedRecallLifecycle:
    queue_id: str
    verification_ref: str
    lifecycle: RecallBotLifecycleEvent
    truth_class: str = "VERIFIED"
    transcript_evidence: bool = False
    predictive_revenue_input: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["lifecycle"] = self.lifecycle.as_dict()
        return data


def route_verified_lifecycle_spool_record(
    record: Mapping[str, Any],
) -> RoutedRecallLifecycle:
    decoded = decode_verified_spool_record(record)
    lifecycle = normalize_verified_recall_lifecycle(
        payload=decoded.payload,
        verified=True,
    )
    return RoutedRecallLifecycle(
        queue_id=decoded.queue_id,
        verification_ref=decoded.verification_ref,
        lifecycle=lifecycle,
    )


def _updated_at(payload: Mapping[str, Any]) -> datetime:
    lifecycle = payload.get("lifecycle")
    if not isinstance(lifecycle, Mapping):
        raise ValueError("lifecycle mapping required")
    raw = str(lifecycle.get("updated_at") or "").strip()
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("lifecycle updated_at must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("lifecycle updated_at must include timezone")
    return parsed.astimezone(timezone.utc)


def _should_replace_latest(path: Path, payload: Mapping[str, Any]) -> bool:
    if not path.is_file():
        return True
    try:
        current = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("existing lifecycle latest snapshot unreadable") from exc
    if not isinstance(current, Mapping):
        raise ValueError("existing lifecycle latest snapshot must be object")
    return _updated_at(payload) >= _updated_at(current)


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


def process_verified_lifecycle_spool(
    *,
    spool_root: str | Path,
    event_root: str | Path,
    latest_root: str | Path,
    max_items: int = 100,
) -> dict[str, Any]:
    source_root = Path(spool_root)
    events = Path(event_root)
    latest = Path(latest_root)
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
            routed = route_verified_lifecycle_spool_record(record)
            event_path = events / f"{routed.queue_id}.json"
            meeting_id = routed.lifecycle.binding.meeting_id
            if event_path.exists():
                duplicates += 1
            else:
                payload = routed.as_dict()
                _atomic_json(event_path, payload)
                latest_path = latest / f"{meeting_id}.json"
                if _should_replace_latest(latest_path, payload):
                    _atomic_json(latest_path, payload)
                processed += 1
                changed_meetings.add(meeting_id)
            source.unlink()
        except Exception:
            failed += 1

    return {
        "processed": processed,
        "failed": failed,
        "duplicates": duplicates,
        "meetings": sorted(changed_meetings),
        "transcript_evidence_written": False,
        "predictive_revenue_input_written": False,
        "execution_authority": "none",
    }
