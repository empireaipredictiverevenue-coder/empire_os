"""Durable rolling context memory for Empire Coder."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .audit import AuditTrail
from .models import CoderTask, utc_now
from .state import LocalTaskStore, compact_task_context


def _bounded_strings(values, limit: int, max_chars: int = 800) -> list[str]:
    out = []
    for value in list(values)[-limit:]:
        text = str(value)
        out.append(text[:max_chars])
    return out


def _compact_event(row: dict[str, Any]) -> dict[str, Any]:
    data = row.get("data") or {}
    safe_data = {}
    for key in (
        "path", "symbol", "provider", "model", "error",
        "output_chars", "revision_count", "actionable",
        "documents", "symbols", "verdict",
    ):
        if key in data:
            safe_data[key] = data[key]
    return {
        "ts": row.get("ts"),
        "event": row.get("event"),
        "data": safe_data,
    }


class ContextMemory:
    """Continuously produces compact, restart-safe task context."""

    def __init__(
        self,
        store: LocalTaskStore,
        audit: AuditTrail,
        *,
        max_events: int = 24,
    ) -> None:
        self.store = store
        self.audit = audit
        self.max_events = max(4, int(max_events))
        self.root = self.store.root / "context"
        self.root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)

    def refresh(
        self,
        task_id: str,
        *,
        trigger: str,
        git_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        task = self.store.load(task_id)
        previous = self.load(task_id)
        version = int((previous or {}).get("version") or 0) + 1
        events = self.audit.read_task(task_id)[-self.max_events:]
        proposal = self.store.latest_proposal(task_id)
        command_proposal = self.store.latest_command_proposal(task_id)

        core = compact_task_context(task)
        core["discovered_files"] = _bounded_strings(
            task.discovered_files, 30, 500
        )
        core["decisions"] = _bounded_strings(task.decisions, 20, 800)
        core["completed_steps"] = _bounded_strings(
            task.completed_steps, 30, 800
        )
        core["unresolved_issues"] = _bounded_strings(
            task.unresolved_issues, 20, 1000
        )
        core["tests_required"] = _bounded_strings(
            task.tests_required, 30, 500
        )
        core["pending_approval"] = _bounded_strings(
            task.pending_approval, 20, 500
        )

        latest_proposal = None
        if proposal:
            latest_proposal = {
                "provider": proposal.get("provider"),
                "model": proposal.get("model"),
                "stage": proposal.get("stage"),
                "revision_count": proposal.get("revision_count"),
                "actionable": proposal.get("actionable"),
                "refined": str(proposal.get("refined") or "")[:4000],
            }

        latest_command = None
        if command_proposal:
            latest_command = {
                "candidate_count": len(
                    command_proposal.get("candidate_texts") or []
                ),
                "critique": str(
                    command_proposal.get("critique") or ""
                )[:2000],
                "argv": list(command_proposal.get("argv") or []),
                "decision": command_proposal.get("decision"),
                "eligible": bool(command_proposal.get("eligible")),
            }

        snapshot = {
            "version": version,
            "updated_at": utc_now(),
            "trigger": trigger,
            "task": core,
            "recent_events": [_compact_event(row) for row in events],
            "latest_proposal": latest_proposal,
            "latest_command_proposal": latest_command,
            "git_state": git_state or {},
            "recovery_instructions": (
                "Resume from task.phase and unresolved_issues. "
                "Re-read files before patching. Re-run pending verification. "
                "Never infer missing production state or bypass approvals."
            ),
        }
        self._write(task, snapshot)
        return snapshot

    def load(self, task_id: str) -> dict[str, Any] | None:
        path = self._path(task_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _write(self, task: CoderTask, snapshot: dict[str, Any]) -> None:
        path = self._path(task.id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.chmod(tmp, 0o600)
        tmp.replace(path)
        os.chmod(path, 0o600)

    def _path(self, task_id: str) -> Path:
        safe = "".join(ch for ch in task_id if ch.isalnum() or ch in "_-")
        if not safe or safe != task_id:
            raise ValueError("invalid task id")
        return self.root / f"{safe}.json"
