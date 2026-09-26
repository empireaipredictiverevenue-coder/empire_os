"""Atomic local task-state store for Empire Coder."""
from __future__ import annotations

import json
import os
from dataclasses import fields
from pathlib import Path
from typing import Any

from .models import (
    CoderTask,
    TaskPhase,
    TaskStatus,
    VerificationVerdict,
    new_id,
    utc_now,
)
from .policy import resolve_runtime_root, resolve_workspace


class TaskStateError(RuntimeError):
    pass


class LocalTaskStore:
    def __init__(
        self,
        workspace: str | Path,
        runtime_root: str | Path | None = None,
    ) -> None:
        self.workspace = resolve_workspace(workspace)
        self.root = resolve_runtime_root(
            self.workspace, runtime_root
        )
        self.tasks_dir = self.root / "tasks"
        self.proposals_dir = self.root / "proposals"
        self.commands_dir = self.root / "command_proposals"
        self.structured_patches_dir = (
            self.root / "structured_patch_proposals"
        )
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.proposals_dir.mkdir(parents=True, exist_ok=True)
        self.commands_dir.mkdir(parents=True, exist_ok=True)
        self.structured_patches_dir.mkdir(
            parents=True,
            exist_ok=True,
        )
        os.chmod(self.root, 0o700)
        os.chmod(self.tasks_dir, 0o700)
        os.chmod(self.proposals_dir, 0o700)
        os.chmod(self.commands_dir, 0o700)
        os.chmod(self.structured_patches_dir, 0o700)

    def create(self, objective: str, *, blueprint_path: str) -> CoderTask:
        text = str(objective or "").strip()
        if not text:
            raise TaskStateError("task objective is required")
        task = CoderTask(
            id=new_id("coder"),
            objective=text,
            workspace=str(self.workspace),
            blueprint_path=blueprint_path,
        )
        self.save(task)
        return task

    def save(self, task: CoderTask) -> None:
        task.updated_at = utc_now()
        path = self._path(task.id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(task.as_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.chmod(tmp, 0o600)
        tmp.replace(path)
        os.chmod(path, 0o600)

    def load(self, task_id: str) -> CoderTask:
        path = self._path(task_id)
        if not path.exists():
            raise TaskStateError(f"unknown task: {task_id}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        allowed = {item.name for item in fields(CoderTask)}
        payload = {key: value for key, value in raw.items() if key in allowed}
        payload["status"] = TaskStatus(payload["status"])
        payload["phase"] = TaskPhase(payload["phase"])
        verdict = payload.get("verification_status")
        payload["verification_status"] = (
            VerificationVerdict(verdict) if verdict else None
        )
        return CoderTask(**payload)

    def save_proposal(
        self,
        task_id: str,
        proposal: dict[str, Any],
    ) -> Path:
        self._path(task_id)
        task_dir = self.proposals_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(task_dir, 0o700)
        revision = int(proposal.get("revision_count") or 0)
        stage = str(proposal.get("stage") or "UNKNOWN")
        filename = f"{revision:04d}_{stage.lower()}.json"
        path = task_dir / filename
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(proposal, indent=2, sort_keys=True) + '\n',
            encoding="utf-8",
        )
        os.chmod(tmp, 0o600)
        tmp.replace(path)
        os.chmod(path, 0o600)
        return path

    def latest_proposal(self, task_id: str) -> dict[str, Any] | None:
        self._path(task_id)
        task_dir = self.proposals_dir / task_id
        if not task_dir.exists():
            return None
        files = sorted(task_dir.glob("*.json"))
        if not files:
            return None
        return json.loads(files[-1].read_text(encoding="utf-8"))

    def save_command_proposal(
        self,
        task_id: str,
        proposal: dict[str, Any],
    ) -> Path:
        self._path(task_id)
        task_dir = self.commands_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(task_dir, 0o700)
        existing = sorted(task_dir.glob("*.json"))
        sequence = len(existing) + 1
        path = task_dir / f"{sequence:04d}_command.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(proposal, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.chmod(tmp, 0o600)
        tmp.replace(path)
        os.chmod(path, 0o600)
        return path

    def latest_command_proposal(
        self,
        task_id: str,
    ) -> dict[str, Any] | None:
        self._path(task_id)
        task_dir = self.commands_dir / task_id
        if not task_dir.exists():
            return None
        files = sorted(task_dir.glob("*.json"))
        if not files:
            return None
        return json.loads(files[-1].read_text(encoding="utf-8"))

    def save_structured_patch_proposal(
        self,
        task_id: str,
        proposal: dict[str, Any],
    ) -> Path:
        self._path(task_id)
        task_dir = self.structured_patches_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(task_dir, 0o700)
        sequence = len(list(task_dir.glob("*.json"))) + 1
        path = task_dir / f"{sequence:04d}_patch.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(proposal, indent=2, sort_keys=True) + '\n',
            encoding="utf-8",
        )
        os.chmod(tmp, 0o600)
        tmp.replace(path)
        os.chmod(path, 0o600)
        return path

    def latest_structured_patch_proposal(
        self,
        task_id: str,
    ) -> dict[str, Any] | None:
        self._path(task_id)
        task_dir = self.structured_patches_dir / task_id
        if not task_dir.exists():
            return None
        files = sorted(task_dir.glob("*.json"))
        if not files:
            return None
        return json.loads(files[-1].read_text(encoding="utf-8"))

    def checkpoint(
        self,
        task: CoderTask,
        *,
        phase: TaskPhase | None = None,
        status: TaskStatus | None = None,
    ) -> CoderTask:
        if phase is not None:
            task.phase = phase
        if status is not None:
            task.status = status
        self.save(task)
        return task

    def _path(self, task_id: str) -> Path:
        safe = "".join(ch for ch in task_id if ch.isalnum() or ch in "_-")
        if not safe or safe != task_id:
            raise TaskStateError("invalid task id")
        return self.tasks_dir / f"{safe}.json"


def compact_task_context(task: CoderTask) -> dict[str, Any]:
    """Return the durable recovery context needed after model compaction."""
    return {
        "task_id": task.id,
        "objective": task.objective,
        "workspace": task.workspace,
        "blueprint_path": task.blueprint_path,
        "status": task.status.value,
        "phase": task.phase.value,
        "plan": list(task.plan),
        "plan_steps": list(task.plan_steps),
        "completed_steps": list(task.completed_steps),
        "unresolved_issues": list(task.unresolved_issues),
        "discovered_files": list(task.discovered_files[-50:]),
        "decisions": list(task.decisions[-50:]),
        "tests_required": list(task.tests_required),
        "verification_status": (
            task.verification_status.value
            if task.verification_status else None
        ),
        "pending_approval": list(task.pending_approval),
    }
