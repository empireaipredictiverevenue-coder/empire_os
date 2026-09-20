"""Durable local job queue for long-running Empire Coder model work."""
from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from .models import utc_now
from .policy import resolve_runtime_root, resolve_workspace


class JobKind(str, Enum):
    PLAN = "PLAN"
    IMPLEMENT = "IMPLEMENT"
    VERIFY = "VERIFY"
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
    priority: int = 50
    attempts: int = 0
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    lease_id: str | None = None
    worker_id: str | None = None
    heartbeat_at: str | None = None
    lease_expires_at: str | None = None
    retry_after: str | None = None
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

    def enqueue(
        self,
        *,
        task_id: str,
        kind: JobKind,
        payload: dict[str, Any] | None = None,
        priority: int = 50,
    ) -> CoderJob:
        job = CoderJob(
            id=f"coder_job_{uuid4().hex}",
            task_id=self._safe_id(task_id),
            kind=JobKind(kind),
            payload=dict(payload or {}),
            priority=max(0, min(int(priority), 100)),
        )
        with self._locked():
            self._write(self.pending / f"{job.id}.json", job)
        return job

    def claim_next(
        self,
        *,
        worker_id: str | None = None,
        lease_seconds: int = 240,
    ) -> CoderJob | None:
        now = datetime.now(timezone.utc)
        lease_for = max(60, int(lease_seconds))
        with self._locked():
            candidates: list[tuple[int, str, Path, CoderJob]] = []
            for source in self.pending.glob("*.json"):
                candidate = self._load_path(source)
                retry_after = self._parse_ts(candidate.retry_after)
                if retry_after is not None and retry_after > now:
                    continue
                candidates.append(
                    (
                        -max(0, min(int(candidate.priority), 100)),
                        str(candidate.created_at or ""),
                        source,
                        candidate,
                    )
                )
            for _, _, source, candidate in sorted(candidates):
                destination = self.running / source.name
                try:
                    source.replace(destination)
                except FileNotFoundError:
                    continue
                job = self._load_path(destination)
                job.status = JobStatus.RUNNING
                job.attempts += 1
                job.error = None
                job.lease_id = f"lease_{uuid4().hex}"
                job.worker_id = str(worker_id or f"pid:{os.getpid()}")
                job.heartbeat_at = now.isoformat()
                job.lease_expires_at = (
                    now + timedelta(seconds=lease_for)
                ).isoformat()
                job.retry_after = None
                job.updated_at = utc_now()
                self._write(destination, job)
                return job
        return None

    def heartbeat(
        self,
        job: CoderJob,
        *,
        lease_seconds: int = 240,
    ) -> CoderJob:
        current = self.running / f"{self._safe_id(job.id)}.json"
        with self._locked():
            if not current.exists():
                return self.get(job.id)
            active = self._load_path(current)
            if job.lease_id and active.lease_id != job.lease_id:
                raise JobQueueError("job lease mismatch")
            now = datetime.now(timezone.utc)
            active.heartbeat_at = now.isoformat()
            active.lease_expires_at = (
                now + timedelta(seconds=max(60, int(lease_seconds)))
            ).isoformat()
            active.updated_at = utc_now()
            self._write(current, active)
            return active

    def retry(
        self,
        job: CoderJob,
        error: str,
        *,
        delay_seconds: int = 30,
        max_attempts: int = 3,
    ) -> CoderJob:
        current = self.running / f"{self._safe_id(job.id)}.json"
        with self._locked():
            if not current.exists():
                return self.get(job.id)
            active = self._load_path(current)
            if job.lease_id and active.lease_id != job.lease_id:
                raise JobQueueError("job lease mismatch")
            now = datetime.now(timezone.utc)
            active.status = JobStatus.PENDING
            active.error = str(error)[:4000]
            retry_delay = max(1, int(delay_seconds))
            if active.attempts >= max(1, int(max_attempts)):
                retry_delay = max(retry_delay, 600)
            active.retry_after = (
                now + timedelta(seconds=retry_delay)
            ).isoformat()
            active.lease_id = None
            active.worker_id = None
            active.heartbeat_at = None
            active.lease_expires_at = None
            active.updated_at = utc_now()
            self._write(current, active)
            destination = self.pending / current.name
            current.replace(destination)
            return active

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
        stale_seconds: int = 240,
        max_attempts: int = 3,
    ) -> list[str]:
        now = datetime.now(timezone.utc)
        recovered: list[str] = []
        with self._locked():
            for path in sorted(self.running.glob("*.json")):
                job = self._load_path(path)
                lease_expires = self._parse_ts(job.lease_expires_at)
                age = now.timestamp() - path.stat().st_mtime
                stale_by_mtime = age >= max(1, int(stale_seconds))
                stale_by_lease = bool(
                    lease_expires is not None and lease_expires <= now
                )
                stale = stale_by_mtime or stale_by_lease
                if not stale:
                    continue
                job.status = JobStatus.PENDING
                job.lease_id = None
                job.worker_id = None
                job.heartbeat_at = None
                job.lease_expires_at = None
                job.error = (
                    "stale_worker_retry_deferred"
                    if job.attempts >= max(1, int(max_attempts))
                    else job.error
                )
                job.retry_after = (
                    (now + timedelta(minutes=10)).isoformat()
                    if job.attempts >= max(1, int(max_attempts))
                    else None
                )
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
        with self._locked():
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
            active = self._load_path(current)
            if job.lease_id and active.lease_id != job.lease_id:
                raise JobQueueError("job lease mismatch")
            job.status = status
            job.result = result
            job.error = error
            job.lease_id = None
            job.worker_id = None
            job.heartbeat_at = None
            job.lease_expires_at = None
            job.retry_after = None
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
    def _parse_ts(value: str | None) -> datetime | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(
                raw[:-1] + "+00:00" if raw.endswith("Z") else raw
            )
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

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
