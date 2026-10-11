"""Read-only Founder API for the canonical Empire execution ledger."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from empire_os.master_execution_ledger import build_execution_ledger


DEFAULT_CHECKLIST = Path(
    "/srv/empire_os/docs/MASTER_REMAINING_CHECKLIST.md"
)
DEFAULT_COMPLETION_PROGRESS = Path(
    "/srv/empire_os/runtime/execution_plane/empire_completion_program_progress.json"
)
DEFAULT_CAPABILITY_REGISTRY = Path(
    "/srv/empire_os/runtime/execution_plane/empire_completion_capability_registry.json"
)
DEFAULT_TASK_MONITOR = Path(
    "/srv/empire_os/runtime/execution_plane/completion_task_monitor_latest.json"
)


def _read_json_artifact(path: Path, label: str) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, f"{label}_missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, f"{label}_invalid"
    if not isinstance(payload, dict):
        return None, f"{label}_invalid"
    return payload, None


def create_founder_execution_ledger_router(
    checklist_path: Path = DEFAULT_CHECKLIST,
    completion_progress_path: Path = DEFAULT_COMPLETION_PROGRESS,
    capability_registry_path: Path = DEFAULT_CAPABILITY_REGISTRY,
    task_monitor_path: Path = DEFAULT_TASK_MONITOR,
) -> APIRouter:
    router = APIRouter(
        prefix="/v1/founder-execution-ledger",
        tags=["founder-execution-ledger"],
    )

    @router.get("/status")
    def status(pending_only: bool = False):
        ledger = build_execution_ledger(checklist_path)
        if pending_only:
            ledger["items"] = [
                item
                for item in ledger["items"]
                if item["status"] == "PENDING"
            ]
        ledger["read_only"] = True
        ledger["execution_authority"] = "none"
        return ledger

    @router.get("/completion-program")
    def completion_program():
        progress, progress_blocker = _read_json_artifact(
            completion_progress_path,
            "completion_progress",
        )
        registry, registry_blocker = _read_json_artifact(
            capability_registry_path,
            "capability_registry",
        )
        blockers = tuple(
            blocker
            for blocker in (progress_blocker, registry_blocker)
            if blocker is not None
        )
        return {
            "schema_version": "empire.founder-completion-program.v1",
            "available": not blockers,
            "blockers": blockers,
            "programme_progress": progress,
            "capability_registry": registry,
            "read_only": True,
            "execution_authority": "none",
        }

    @router.get("/task-monitor")
    def task_monitor(
        department: str | None = None,
        state: str | None = None,
        limit: int = 100,
    ):
        # Read the existing department-cycle snapshot only. No task claims,
        # outbound notifications, queue writes or implementation authority.
        from empire_os.completion_task_monitor import SCHEMA, _stamp
        snapshot, blocked = _read_json_artifact(
            task_monitor_path, "task_monitor",
        )
        if blocked is not None or snapshot is None:
            return {
                "available": False, "reason": blocked,
                "read_only": True, "execution_authority": "none",
            }
        generated_at = snapshot.get("generated_at")
        try:
            stamped = _stamp(generated_at)
        except ValueError:
            stamped = None
        current = datetime.now(timezone.utc)
        if (snapshot.get("schema_version") != SCHEMA
                or snapshot.get("status") != "AVAILABLE"
                or snapshot.get("execution_authority") != "none"
                or snapshot.get("monitoring_not_dispatch") is not True
                or snapshot.get("external_execution_performed") is not False
                or not isinstance(snapshot.get("items"), list)
                or stamped is None
                or stamped > current + timedelta(minutes=2)
                or current - stamped > timedelta(minutes=20)):
            return {
                "available": False,
                "reason": "task_monitor_snapshot_stale_or_untrusted",
                "last_observed_at": generated_at,
                "read_only": True, "execution_authority": "none",
            }
        if type(limit) is not int or not 1 <= limit <= 200:
            return {
                "available": False, "reason": "invalid_limit",
                "read_only": True, "execution_authority": "none",
            }
        items = snapshot["items"]
        if (len(items) != snapshot.get("tracked_pending_count")
                or any(not isinstance(row, dict) for row in items)):
            return {
                "available": False, "reason": "task_monitor_item_count_invalid",
                "read_only": True, "execution_authority": "none",
            }
        if department:
            items = [row for row in items if row.get("department") == department]
        if state:
            items = [row for row in items if row.get("state") == state]
        return {
            "schema_version": SCHEMA,
            "available": True,
            "generated_at": generated_at,
            "checklist": snapshot.get("checklist"),
            "state_counts": snapshot.get("state_counts"),
            "department_counts": snapshot.get("department_counts"),
            "tracked_pending_count": snapshot.get("tracked_pending_count"),
            "attention_count": snapshot.get("attention_count"),
            "top_attention": snapshot.get("top_attention"),
            "new_state_transition_count": snapshot.get("new_state_transition_count"),
            "new_state_transitions": snapshot.get("new_state_transitions"),
            "recent_transitions": snapshot.get("recent_transitions"),
            "matched_item_count": len(items),
            "returned_item_count": min(len(items), limit),
            "items": items[:limit],
            "read_only": True,
            "execution_authority": "none",
        }

    return router
