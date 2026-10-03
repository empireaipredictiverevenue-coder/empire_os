"""Live queue and completion truth for EmpireOS.

Separates canonical checklist backlog from actual runnable queues. Historical
failed jobs are reported separately and never counted as active work.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from empire_os.coder.plan_fastpath import classify_fast_plan
from empire_os.completion_progress import checklist_counts


SCHEMA_VERSION = "empire.live_queue_truth.v1"
OUTPUT = Path("runtime/execution_plane/live_queue_truth_latest.json")


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def _coder_counts(root: Path) -> dict[str, Any]:
    jobs_root = root / "runtime/coder/jobs"
    counts: dict[str, dict[str, int]] = {}
    for bucket in ("pending", "running", "delegated", "completed", "failed"):
        kind_counts: Counter[str] = Counter()
        for path in (jobs_root / bucket).glob("*.json"):
            packet = _read_json(path)
            if packet is None:
                continue
            kind_counts[str(packet.get("kind") or "UNKNOWN")] += 1
        counts[bucket] = dict(sorted(kind_counts.items()))

    fastpath_eligible = 0
    model_plan_pending = 0
    unreadable_plan_jobs = 0
    tasks_root = root / "runtime/coder/tasks"
    for path in (jobs_root / "pending").glob("*.json"):
        job = _read_json(path)
        if not job or job.get("kind") != "PLAN":
            continue
        task_id = str(job.get("task_id") or "").strip()
        task = _read_json(tasks_root / f"{task_id}.json")
        if task is None:
            unreadable_plan_jobs += 1
            continue
        family = classify_fast_plan(
            str(task.get("objective") or ""),
            job.get("payload") or {},
        )
        if family is not None:
            fastpath_eligible += 1
        else:
            model_plan_pending += 1

    active_pending = sum(counts["pending"].values())
    active_running = sum(counts["running"].values())
    active_delegated = sum(counts["delegated"].values())
    return {
        "buckets": counts,
        "active_pending_count": active_pending,
        "active_running_count": active_running,
        "active_delegated_count": active_delegated,
        "fastpath_plan_pending_count": fastpath_eligible,
        "local_model_plan_pending_count": model_plan_pending,
        "unreadable_plan_pending_count": unreadable_plan_jobs,
        "verify_pending_count": int(counts["pending"].get("VERIFY", 0)),
        "historical_failed_count": sum(counts["failed"].values()),
        "historical_failed_is_active_backlog": False,
    }


def _department_counts(root: Path) -> dict[str, int]:
    base = root / "runtime/departments/work"
    return {
        bucket: len(list((base / bucket).glob("*.json")))
        for bucket in (
            "ready",
            "running",
            "review",
            "done",
            "blocked",
            "failed",
        )
    }


def build_live_queue_truth(
    repo_root: str | Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    checklist_path = root / "docs/MASTER_REMAINING_CHECKLIST.md"
    checklist = (
        checklist_counts(checklist_path)
        if checklist_path.exists()
        else {
            "master_checklist_done": 0,
            "master_checklist_pending": 0,
            "master_checklist_total": 0,
        }
    )
    coder = _coder_counts(root)
    departments = _department_counts(root)

    allocation_path = (
        root
        / "runtime/execution_plane/business_completion_allocation_latest.json"
    )
    allocation = _read_json(allocation_path) or {}
    allocation_mtime = (
        datetime.fromtimestamp(
            allocation_path.stat().st_mtime,
            tz=timezone.utc,
        )
        if allocation_path.exists()
        else None
    )
    allocation_age_seconds = (
        max(0.0, (current - allocation_mtime).total_seconds())
        if allocation_mtime is not None
        else None
    )
    allocation_stale = (
        allocation_age_seconds is None
        or allocation_age_seconds > 900
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "generated_at": current.isoformat(),
        "canonical_checklist": {
            "done": checklist["master_checklist_done"],
            "pending": checklist["master_checklist_pending"],
            "total": checklist["master_checklist_total"],
            "meaning": "business_completion_scope_not_runnable_queue",
        },
        "department_work_queue": {
            **departments,
            "active_count": (
                departments["ready"]
                + departments["running"]
                + departments["review"]
            ),
        },
        "coder_queue": coder,
        "legacy_completion_allocation_snapshot": {
            "reported_pending_count": allocation.get("pending_count"),
            "generated_at": allocation.get("generated_at"),
            "age_seconds": (
                round(allocation_age_seconds, 3)
                if allocation_age_seconds is not None
                else None
            ),
            "stale": allocation_stale,
            "use_as_live_queue_count": False,
        },
        "active_execution_backlog": (
            departments["ready"]
            + departments["running"]
            + coder["active_pending_count"]
            + coder["active_running_count"]
            + coder["active_delegated_count"]
        ),
        "automation": {
            "deterministic_plan_fastpath": True,
            "local_model_plan_worker": True,
            "department_heartbeat": True,
            "historical_failures_auto_counted_as_active": False,
        },
        "execution_authority": "none",
    }
    _atomic_write(root / OUTPUT, payload)
    return payload
