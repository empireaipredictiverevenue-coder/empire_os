"""Read-only Founder API for the canonical Empire execution ledger."""
from __future__ import annotations

import json
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

    return router
