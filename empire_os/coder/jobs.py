"""Durable local job queue for long-running Empire Coder model work."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from .models import utc_now
from .policy import resolve_runtime_root, resolve_workspace


class JobKind(str, Enum):
    PLAN = "PLAN"
    IMPLEMENT = "IMPLEMENT"
    NEXT_COMMAND = "NEXT_COMMAND"


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class CoderJob:
    id: str
    task_id: str
    kind: JobKind
    payload: dict[str, Any] = field(default_factory=dict)
    status: JobStatus = JobStatus.PENDING
    attempts: int = 0
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["kind"] = self.kind.value
        data["status"] = self.status.value
        return data


class JobQueueError(RuntimeError):
    pass


class LocalJobQueue:
    def __init__(
        self,
        workspace: str | Path,
        *,
        runtime_root: str | Path | None = None,
    ) -> None:
        self.workspace = resolve_workspace(workspace)
        self.runtime_root = resolve_runtime_root(
            self.workspace, runtime_root
        )
        self.root = self.runtime_root / "jobs"
        self.pending = self.root / "pending"
        self.running = self.root / "running"
        self.completed = self.root / "completed"
        self.failed = self.root / "failed"
        for directory in (
            self.root,
            self.pending,
            self.running,
            self.completed,
            self.failed,
        ):
            directory.mkdir(parents=True, exist_ok=True)
            os.chmod(directory, 0o700)

    def enqueue(
        self,
        *,
        task_id: str,
        kind: JobKind,
        payload: dict[str, Any] | None = None,
    ) -> CoderJob:
        job = CoderJob(
            id=f"coder_job_{uuid4().hex}",
            task_id=self._safe_id(task_id),
            kind=JobKind(kind),
            payload=dict(payload or {}),
        )
        self._write(self.pending / f"{job.id}.json", job)
        return job

    def claim_next(self) -> CoderJob | None:
        for source in sorted(self.pending.glob("*.json")):
            destination = self.running / source.name
            try:
                source.replace(destination)
            except FileNotFoundError:
                continue
            job = self._load_path(destination)
            job.status = JobStatus.RUNNING
            job.attempts += 1
            job.updated_at = utc_now()
            self._write(destination, job)
            return job
        return None

    def complete(
        self,
        job: CoderJob,
        result: dict[str, Any] | None = None,
    ) -> CoderJob:
        return self._finish(
            job,
            status=JobStatus.COMPLETED,
            result=dict(result or {}),
            error=None,
        )

    def fail(self, job: CoderJob, error: str) -> CoderJob:
        return self._finish(
            job,
            status=JobStatus.FAILED,
            result={},
            error=str(error)[:4000],
        )

    def get(self, job_id: str) -> CoderJob:
        safe = self._safe_id(job_id)
        for directory in (
            self.pending,
            self.running,
            self.completed,
            self.failed,
        ):
            path = directory / f"{safe}.json"
            if path.exists():
                return self._load_path(path)
        raise JobQueueError(f"unknown job: {safe}")

    def recover_stale(
        self,
        *,
        stale_seconds: int = 1800,
        max_attempts: int = 3,
    ) -> list[str]:
        now = datetime.now(timezone.utc).timestamp()
        recovered: list[str] = []
        for path in sorted(self.running.glob("*.json")):
            age = now - path.stat().st_mtime
            if age < max(1, int(stale_seconds)):
                continue
            job = self._load_path(path)
            if job.attempts >= max(1, int(max_attempts)):
                self.fail(job, "stale_job_attempt_limit_reached")
                continue
            job.status = JobStatus.PENDING
            job.updated_at = utc_now()
            destination = self.pending / path.name
            self._write(path, job)
            path.replace(destination)
            recovered.append(job.id)
        return recovered

    def _finish(
        self,
        job: CoderJob,
        *,
        status: JobStatus,
        result: dict[str, Any],
        error: str | None,
    ) -> CoderJob:
        current = self.running / f"{self._safe_id(job.id)}.json"
        if not current.exists():
            name = f"{self._safe_id(job.id)}.json"
            for directory in (
                self.completed,
                self.failed,
                self.pending,
            ):
                existing = directory / name
                if existing.exists():
                    return self._load_path(existing)
            raise JobQueueError("job is not currently running")
        job.status = status
        job.result = result
        job.error = error
        job.updated_at = utc_now()
        target_dir = (
            self.completed
            if status is JobStatus.COMPLETED
            else self.failed
        )
        self._write(current, job)
        current.replace(target_dir / current.name)
        return job

    @staticmethod
    def _safe_id(value: str) -> str:
        raw = str(value or "")
        safe = "".join(
            ch for ch in raw if ch.isalnum() or ch in "_-"
        )
        if not safe or safe != raw:
            raise JobQueueError("invalid job/task id")
        return safe

    @staticmethod
    def _write(path: Path, job: CoderJob) -> None:
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(job.as_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.chmod(tmp, 0o600)
        tmp.replace(path)
        os.chmod(path, 0o600)

    @staticmethod
    def _load_path(path: Path) -> CoderJob:
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["kind"] = JobKind(raw["kind"])
        raw["status"] = JobStatus(raw["status"])
        return CoderJob(**raw)
