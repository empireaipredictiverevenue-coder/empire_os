"""Durable work queue for Astra-delegated department work.

Work is persistent, deduplicated, atomically leased and authority preserving.
A queue item does not itself create external execution authority.
"""
from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4


class DepartmentWorkStatus(str, Enum):
    READY = "READY"
    RUNNING = "RUNNING"
    REVIEW = "REVIEW"
    DONE = "DONE"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


@dataclass
class DepartmentWorkItem:
    id: str
    plan_id: str
    step_id: str
    goal_key: str
    department_keys: tuple[str, ...]
    target_component: str
    action: str
    authority: str
    priority: int
    intelligence_request: dict[str, Any] = field(default_factory=dict)
    memory_query: dict[str, Any] = field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()
    success_condition: str = ""
    rationale: str = ""
    status: DepartmentWorkStatus = DepartmentWorkStatus.READY
    attempts: int = 0
    result: dict[str, Any] = field(default_factory=dict)
    result_evidence_refs: tuple[str, ...] = ()
    error: str | None = None
    lease_id: str | None = None
    worker_id: str | None = None
    lease_expires_at: str | None = None
    created_at: str = ""
    updated_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["department_keys"] = list(self.department_keys)
        data["evidence_refs"] = list(self.evidence_refs)
        data["result_evidence_refs"] = list(self.result_evidence_refs)
        return data


class DepartmentWorkQueueError(RuntimeError):
    pass


class DepartmentWorkQueue:
    def __init__(self, repo_root: str | Path) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.root = self.repo_root / "runtime" / "departments" / "work"
        self.ready = self.root / "ready"
        self.running = self.root / "running"
        self.review = self.root / "review"
        self.done = self.root / "done"
        self.blocked = self.root / "blocked"
        self.failed = self.root / "failed"
        for path in (
            self.root,
            self.ready,
            self.running,
            self.review,
            self.done,
            self.blocked,
            self.failed,
        ):
            path.mkdir(parents=True, exist_ok=True)
            os.chmod(path, 0o700)
        self.lock_path = self.root / ".queue.lock"
        self.lock_path.touch(exist_ok=True)
        os.chmod(self.lock_path, 0o600)

    @contextmanager
    def _locked(self):
        with self.lock_path.open("r+") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _safe(value: str) -> str:
        raw = str(value or "")
        safe = "".join(
            char for char in raw if char.isalnum() or char in "_-"
        )
        if not safe or safe != raw:
            raise DepartmentWorkQueueError("invalid work identifier")
        return safe

    @staticmethod
    def deterministic_id(plan_id: str, step_id: str) -> str:
        material = f"{plan_id}|{step_id}".encode("utf-8")
        return "dept_work_" + sha256(material).hexdigest()[:24]

    def _directories(self) -> tuple[Path, ...]:
        return (
            self.ready,
            self.running,
            self.review,
            self.done,
            self.blocked,
            self.failed,
        )

    def _find_path(self, work_id: str) -> Path | None:
        safe = self._safe(work_id)
        for directory in self._directories():
            path = directory / f"{safe}.json"
            if path.exists():
                return path
        return None

    def enqueue_step(
        self,
        *,
        plan_id: str,
        step: Mapping[str, Any],
        priority: int = 50,
    ) -> tuple[DepartmentWorkItem, bool]:
        plan = self._safe(str(plan_id or ""))
        step_id = self._safe(str(step.get("step_id") or ""))
        work_id = self.deterministic_id(plan, step_id)
        now = self._now()
        item = DepartmentWorkItem(
            id=work_id,
            plan_id=plan,
            step_id=step_id,
            goal_key=str(step.get("goal_key") or "").strip(),
            department_keys=tuple(
                str(value).strip()
                for value in (step.get("department_keys") or [])
                if str(value).strip()
            ),
            target_component=str(
                step.get("target_component") or ""
            ).strip(),
            action=str(step.get("action") or "").strip(),
            authority=str(step.get("authority") or "").strip(),
            priority=max(0, min(int(priority), 100)),
            intelligence_request=dict(
                step.get("intelligence_request") or {}
            ),
            memory_query=dict(step.get("memory_query") or {}),
            evidence_refs=tuple(
                str(value).strip()
                for value in (step.get("evidence_refs") or [])
                if str(value).strip()
            ),
            success_condition=str(
                step.get("success_condition") or ""
            ).strip(),
            rationale=str(step.get("rationale") or "").strip(),
            created_at=now,
            updated_at=now,
        )

        with self._locked():
            existing = self._find_path(work_id)
            if existing is not None:
                return self._load(existing), False
            self._write(self.ready / f"{work_id}.json", item)
        return item, True

    def claim_next(
        self,
        *,
        worker_id: str | None = None,
        lease_seconds: int = 300,
    ) -> DepartmentWorkItem | None:
        now = datetime.now(timezone.utc)
        with self._locked():
            candidates: list[
                tuple[int, str, Path, DepartmentWorkItem]
            ] = []
            for path in self.ready.glob("*.json"):
                item = self._load(path)
                candidates.append(
                    (-item.priority, item.created_at, path, item)
                )
            for _, _, source, _ in sorted(candidates):
                destination = self.running / source.name
                try:
                    source.replace(destination)
                except FileNotFoundError:
                    continue
                item = self._load(destination)
                item.status = DepartmentWorkStatus.RUNNING
                item.attempts += 1
                item.lease_id = f"lease_{uuid4().hex}"
                item.worker_id = str(
                    worker_id or f"pid:{os.getpid()}"
                )
                item.lease_expires_at = (
                    now + timedelta(
                        seconds=max(60, int(lease_seconds))
                    )
                ).isoformat()
                item.updated_at = self._now()
                self._write(destination, item)
                return item
        return None

    def complete(
        self,
        item: DepartmentWorkItem,
        result: Mapping[str, Any] | None = None,
        *,
        evidence_refs: tuple[str, ...] = (),
    ) -> DepartmentWorkItem:
        return self._finish(
            item,
            DepartmentWorkStatus.DONE,
            dict(result or {}),
            tuple(evidence_refs),
            None,
        )

    def block(
        self,
        item: DepartmentWorkItem,
        reason: str,
        result: Mapping[str, Any] | None = None,
    ) -> DepartmentWorkItem:
        payload = dict(result or {})
        payload.setdefault("blocker", str(reason))
        return self._finish(
            item,
            DepartmentWorkStatus.BLOCKED,
            payload,
            (),
            str(reason),
        )

    def fail(
        self,
        item: DepartmentWorkItem,
        error: str,
    ) -> DepartmentWorkItem:
        return self._finish(
            item,
            DepartmentWorkStatus.FAILED,
            {},
            (),
            str(error),
        )

    def _finish(
        self,
        item: DepartmentWorkItem,
        status: DepartmentWorkStatus,
        result: dict[str, Any],
        evidence_refs: tuple[str, ...],
        error: str | None,
    ) -> DepartmentWorkItem:
        current = self.running / f"{self._safe(item.id)}.json"
        with self._locked():
            if not current.exists():
                existing = self._find_path(item.id)
                if existing is not None:
                    return self._load(existing)
                raise DepartmentWorkQueueError(
                    "work item is not currently running"
                )
            active = self._load(current)
            if item.lease_id and active.lease_id != item.lease_id:
                raise DepartmentWorkQueueError("work lease mismatch")
            active.status = status
            active.result = result
            active.result_evidence_refs = tuple(evidence_refs)
            active.error = error[:4000] if error else None
            active.lease_id = None
            active.worker_id = None
            active.lease_expires_at = None
            active.updated_at = self._now()
            target = {
                DepartmentWorkStatus.DONE: self.done,
                DepartmentWorkStatus.BLOCKED: self.blocked,
                DepartmentWorkStatus.FAILED: self.failed,
                DepartmentWorkStatus.REVIEW: self.review,
            }[status]
            self._write(current, active)
            current.replace(target / current.name)
            return active

    def recover_stale(
        self,
        *,
        max_attempts: int = 3,
    ) -> list[str]:
        now = datetime.now(timezone.utc)
        recovered: list[str] = []
        with self._locked():
            for path in sorted(self.running.glob("*.json")):
                item = self._load(path)
                raw = str(item.lease_expires_at or "").strip()
                if not raw:
                    continue
                try:
                    expiry = datetime.fromisoformat(raw)
                except ValueError:
                    continue
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                if expiry > now:
                    continue
                if item.attempts >= max(1, int(max_attempts)):
                    item.status = DepartmentWorkStatus.FAILED
                    item.error = "max_attempts_exhausted"
                    target = self.failed / path.name
                else:
                    item.status = DepartmentWorkStatus.READY
                    item.error = "stale_worker_recovered"
                    target = self.ready / path.name
                item.lease_id = None
                item.worker_id = None
                item.lease_expires_at = None
                item.updated_at = self._now()
                self._write(path, item)
                path.replace(target)
                recovered.append(item.id)
        return recovered

    def counts(self) -> dict[str, int]:
        return {
            "ready": len(list(self.ready.glob("*.json"))),
            "running": len(list(self.running.glob("*.json"))),
            "review": len(list(self.review.glob("*.json"))),
            "done": len(list(self.done.glob("*.json"))),
            "blocked": len(list(self.blocked.glob("*.json"))),
            "failed": len(list(self.failed.glob("*.json"))),
        }

    @staticmethod
    def _write(path: Path, item: DepartmentWorkItem) -> None:
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(item.as_dict(), indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        os.chmod(tmp, 0o600)
        tmp.replace(path)
        os.chmod(path, 0o600)

    @staticmethod
    def _load(path: Path) -> DepartmentWorkItem:
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["status"] = DepartmentWorkStatus(raw["status"])
        raw["department_keys"] = tuple(raw.get("department_keys") or ())
        raw["evidence_refs"] = tuple(raw.get("evidence_refs") or ())
        raw["result_evidence_refs"] = tuple(
            raw.get("result_evidence_refs") or ()
        )
        return DepartmentWorkItem(**raw)
