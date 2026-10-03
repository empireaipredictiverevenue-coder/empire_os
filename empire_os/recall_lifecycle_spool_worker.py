"""Materialize verified Recall bot status spool into lifecycle evidence."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.recall_bot_lifecycle import normalize_verified_recall_lifecycle
from empire_os.recall_verified_spool import decode_verified_spool_record


@dataclass(frozen=True)
class RecallLifecycleRecord:
    queue_id: str
    lifecycle: Mapping[str, Any]
    source_payload_sha256: str
    source_verification: Mapping[str, Any]
    truth_class: str = "VERIFIED"
    polling_performed: bool = False
    commercial_truth_written: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_lifecycle_record_from_spool(
    *,
    spool_path: str | Path,
) -> RecallLifecycleRecord:
    try:
        raw_record = json.loads(
            Path(spool_path).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Recall lifecycle spool record unreadable") from exc
    if not isinstance(raw_record, Mapping):
        raise ValueError("Recall lifecycle spool record must be an object")

    decoded = decode_verified_spool_record(raw_record)
    lifecycle = normalize_verified_recall_lifecycle(
        payload=decoded.payload,
        verified=True,
    )
    return RecallLifecycleRecord(
        queue_id=decoded.queue_id,
        lifecycle=lifecycle.as_dict(),
        source_payload_sha256=decoded.payload_sha256,
        source_verification=dict(decoded.verification),
    )


def materialize_lifecycle_record(
    *,
    spool_path: str | Path,
    output_root: str | Path,
) -> Path:
    lifecycle = build_lifecycle_record_from_spool(spool_path=spool_path)
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = root / f"{lifecycle.queue_id}.json"
    if target.exists():
        return target


    tmp = root / f".{lifecycle.queue_id}.tmp"
    tmp.write_text(
        json.dumps(lifecycle.as_dict(), sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
    )
    tmp.chmod(0o600)
    tmp.replace(target)
    target.chmod(0o600)
    return target


def process_verified_lifecycle_spool(
    *,
    spool_root: str | Path,
    lifecycle_root: str | Path,
    max_items: int = 100,
) -> dict[str, Any]:
    source_root = Path(spool_root)
    target_root = Path(lifecycle_root)
    processed = 0
    failed = 0
    duplicates = 0
    meetings: set[str] = set()

    if not source_root.is_dir():
        return {
            "processed": 0,
            "failed": 0,
            "duplicates": 0,
            "meetings": [],
            "polling_performed": False,
            "execution_authority": "none",
        }

    for source in sorted(source_root.glob("*.json"))[: max(0, int(max_items))]:
        try:
            record = build_lifecycle_record_from_spool(spool_path=source)
            meeting_id = str(
                (record.lifecycle.get("binding") or {}).get("meeting_id") or ""
            ).strip()
            target = target_root / f"{record.queue_id}.json"
            if target.exists():
                duplicates += 1
            else:
                materialize_lifecycle_record(
                    spool_path=source,
                    output_root=target_root,
                )
                processed += 1
                if meeting_id:
                    meetings.add(meeting_id)
            source.unlink()
        except Exception:
            failed += 1

    return {
        "processed": processed,
        "failed": failed,
        "duplicates": duplicates,
        "meetings": sorted(meetings),
        "polling_performed": False,
        "commercial_truth_written": False,
        "execution_authority": "none",
    }
