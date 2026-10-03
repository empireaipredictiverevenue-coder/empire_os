"""Self-heal failed completion VERIFY jobs after relevant content changes."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.coder.jobs import JobKind, LocalJobQueue
from empire_os.completion_reconciliation import (
    refresh_completion_reconciliation,
)


SCHEMA_VERSION = "empire.completion_verify_recovery.v1"
OUTPUT = Path(
    "runtime/execution_plane/completion_verify_recovery_latest.json"
)


def _read(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def _content_fingerprint(
    root: Path,
    paths: list[str],
) -> str:
    digest = sha256()
    for rel in sorted(set(paths)):
        digest.update(rel.encode("utf-8"))
        path = root / rel
        try:
            digest.update(path.read_bytes())
        except OSError:
            digest.update(b"<MISSING>")
    return digest.hexdigest()


def _existing_keys(queue: LocalJobQueue) -> set[str]:
    keys: set[str] = set()
    for directory in (
        queue.pending,
        queue.running,
        queue.delegated,
        queue.completed,
        queue.failed,
    ):
        for path in directory.glob("*.json"):
            packet = _read(path)
            if packet is None:
                continue
            key = str(
                (packet.get("payload") or {}).get(
                    "completion_verify_recovery_key"
                )
                or ""
            ).strip()
            if key:
                keys.add(key)
    return keys


def recover_failed_completion_verifications(
    repo_root: str | Path,
    *,
    reconciliation: Mapping[str, Any] | None = None,
    max_groups: int = 8,
    now: datetime | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    recon = (
        dict(reconciliation)
        if isinstance(reconciliation, Mapping)
        else refresh_completion_reconciliation(root)
    )
    unresolved = {
        str(row.get("item_id") or "").strip()
        for row in (recon.get("items") or ())
        if isinstance(row, Mapping)
        and row.get("state") == "NEEDS_WIRING_OR_TEST_FIX"
        and str(row.get("item_id") or "").strip()
    }

    queue = LocalJobQueue(root)
    existing_keys = _existing_keys(queue)
    candidates: list[dict[str, Any]] = []

    for path in queue.failed.glob("*.json"):
        job = _read(path)
        if job is None or job.get("kind") != "VERIFY":
            continue
        source = dict(job.get("payload") or {})
        item_ids = [
            str(value).strip()
            for value in (source.get("completion_item_ids") or ())
            if str(value).strip()
        ]
        unresolved_ids = [
            item_id for item_id in item_ids
            if item_id in unresolved
        ]
        if not unresolved_ids:
            continue
        tests = [
            str(value).strip()
            for value in (source.get("tests") or ())
            if str(value).strip()
        ]
        changed_files = [
            str(value).strip()
            for value in (source.get("changed_files") or ())
            if str(value).strip()
        ]
        if not tests or not changed_files:
            continue

        content_fp = _content_fingerprint(root, changed_files + tests)
        key_material = "|".join([
            str(job.get("id") or ""),
            content_fp,
            ",".join(sorted(unresolved_ids)),
        ])
        recovery_key = sha256(key_material.encode("utf-8")).hexdigest()
        if recovery_key in existing_keys:
            continue

        candidates.append({
            "job": job,
            "source": source,
            "unresolved_ids": unresolved_ids,
            "content_fingerprint": content_fp,
            "recovery_key": recovery_key,
        })

    queued: list[dict[str, Any]] = []
    bounded = max(1, min(int(max_groups), 16))
    for row in sorted(
        candidates,
        key=lambda value: (
            -int(value["job"].get("priority") or 0),
            str(value["job"].get("updated_at") or ""),
        ),
    )[:bounded]:
        source = dict(row["source"])
        source["completion_item_ids"] = row["unresolved_ids"]
        source["completion_verify_recovery_key"] = row["recovery_key"]
        source["recovery_of_verify_job_id"] = row["job"].get("id")
        source["recovery_source_content_fingerprint"] = row[
            "content_fingerprint"
        ]
        source["execution_authority"] = "none"

        original_ids = [
            str(value).strip()
            for value in (row["source"].get("completion_item_ids") or ())
        ]
        original_lines = list(
            row["source"].get("completion_checklist_lines") or ()
        )
        line_by_id = {
            item_id: original_lines[index]
            for index, item_id in enumerate(original_ids)
            if index < len(original_lines)
        }
        source["completion_checklist_lines"] = [
            line_by_id[item_id]
            for item_id in row["unresolved_ids"]
            if item_id in line_by_id
        ]

        next_job = queue.enqueue(
            task_id=str(row["job"].get("task_id") or ""),
            kind=JobKind.VERIFY,
            payload=source,
            priority=int(row["job"].get("priority") or 50),
        )
        existing_keys.add(row["recovery_key"])
        queued.append({
            "source_verify_job_id": row["job"].get("id"),
            "recovery_verify_job_id": next_job.id,
            "item_count": len(row["unresolved_ids"]),
            "content_fingerprint": row["content_fingerprint"],
        })


    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "mode": "OBSERVE",
        "generated_at": current.isoformat(),
        "unresolved_item_count": len(unresolved),
        "candidate_group_count": len(candidates),
        "queued_group_count": len(queued),
        "queued_item_count": sum(
            row["item_count"] for row in queued
        ),
        "queued": queued,
        "retry_only_after_relevant_content_change": True,
        "model_inference": False,
        "production_mutation": False,
        "external_execution_performed": False,
        "execution_authority": "none",
    }
    _atomic_write(root / OUTPUT, payload)
    return payload
