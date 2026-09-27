"""Append-only local engineering audit trail."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .models import utc_now
from .security import scrub_text


class AuditTrail:
    def __init__(
        self,
        runtime_root: str | Path,
    ) -> None:
        self.root = Path(runtime_root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        self.path = self.root / "audit.jsonl"

    def record(
        self,
        *,
        task_id: str,
        event: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "ts": utc_now(),
            "task_id": task_id,
            "event": event,
            "data": self._scrub(data or {}),
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, sort_keys=True) + "\n")
        os.chmod(self.path, 0o600)

    def read_task(self, task_id: str) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("task_id") == task_id:
                rows.append(row)
        return rows

    @staticmethod
    def _scrub(value: Any) -> Any:
        if isinstance(value, str):
            return scrub_text(value)
        if isinstance(value, dict):
            return {
                str(key): AuditTrail._scrub(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [AuditTrail._scrub(item) for item in value]
        if isinstance(value, tuple):
            return [AuditTrail._scrub(item) for item in value]
        return value
