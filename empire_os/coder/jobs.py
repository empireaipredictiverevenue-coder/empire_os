"""Durable local job queue for long-running Empire Coder model work."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import subprocess
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
    DELEGATED = "DELEGATED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    RELEASED = "RELEASED"
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
        self.delegated = self.root / "delegated"
        self.awaiting_approval = self.root / "awaiting_approval"
        self.released = self.root / "released"
        self.completed = self.root / "completed"
        self.failed = self.root / "failed"
        for directory in (
            self.root,
            self.pending,
            self.running,
            self.delegated,
            self.awaiting_approval,
            self.released,
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

    def list_pending(
        self,
        *,
        kind: JobKind | None = None,
    ) -> list[CoderJob]:
        with self._locked():
            jobs = [
                self._load_path(path)
                for path in self.pending.glob("*.json")
            ]
        if kind is not None:
            wanted = JobKind(kind)
            jobs = [job for job in jobs if job.kind is wanted]
        return sorted(
            jobs,
            key=lambda job: (
                -max(0, min(int(job.priority), 100)),
                str(job.created_at or ""),
                job.id,
            ),
        )

    def quarantine_exhausted(
        self,
        *,
        max_attempts: int = 3,
    ) -> list[str]:
        """Move pending jobs that already exhausted retries out of the hot queue."""
        exhausted: list[str] = []
        threshold = max(1, int(max_attempts))
        with self._locked():
            for path in sorted(self.pending.glob("*.json")):
                job = self._load_path(path)
                if int(job.attempts or 0) < threshold:
                    continue
                if not str(job.error or "").strip():
                    continue
                job.status = JobStatus.FAILED
                if "max_attempts_exhausted" not in str(job.error):
                    job.error = (
                        f"{str(job.error)[:3900]}:max_attempts_exhausted"
                    )
                job.retry_after = None
                job.lease_id = None
                job.worker_id = None
                job.heartbeat_at = None
                job.lease_expires_at = None
                job.updated_at = utc_now()
                self._write(path, job)
                destination = self.failed / path.name
                path.replace(destination)
                exhausted.append(job.id)
        return exhausted

    def claim_next(
        self,
        *,
        worker_id: str | None = None,
        lease_seconds: int = 240,
        kind: JobKind | None = None,
    ) -> CoderJob | None:
        now = datetime.now(timezone.utc)
        lease_for = max(60, int(lease_seconds))
        with self._locked():
            candidates: list[tuple[int, str, Path, CoderJob]] = []
            for source in self.pending.glob("*.json"):
                candidate = self._load_path(source)
                if kind is not None and candidate.kind is not kind:
                    continue
                # A governed implementation intake is an isolated PROPOSAL
                # request, not permission for this shared-worktree worker to
                # patch live source. It requires the original execution-plane
                # sandbox/release owner, never automatic local claim_next.
                if (
                    candidate.kind is JobKind.IMPLEMENT
                    and candidate.payload.get("execution_mode")
                    == "ISOLATED_CANDIDATE_ONLY"
                ):
                    continue
                # Observation-only Swarm jobs belong to the dedicated
                # test fast-path, never the task-aware implementation worker.
                if (
                    candidate.kind is JobKind.VERIFY
                    and candidate.payload.get("verification_scope") == "TEST_EXECUTION_ONLY"
                ):
                    continue
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

    def claim_specific(
        self,
        job_id: str,
        *,
        worker_id: str | None = None,
        lease_seconds: int = 240,
    ) -> CoderJob | None:
        """Atomically claim one known pending job without disturbing queue order."""
        safe = self._safe_id(job_id)
        source = self.pending / f"{safe}.json"
        now = datetime.now(timezone.utc)
        lease_for = max(60, int(lease_seconds))
        with self._locked():
            if not source.exists():
                return None
            candidate = self._load_path(source)
            retry_after = self._parse_ts(candidate.retry_after)
            if retry_after is not None and retry_after > now:
                return None
            destination = self.running / source.name
            try:
                source.replace(destination)
            except FileNotFoundError:
                return None
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

    def delegate_pending(
        self,
        job_id: str,
        *,
        delegation: dict[str, Any],
    ) -> CoderJob:
        safe = self._safe_id(job_id)
        source = self.pending / f"{safe}.json"
        with self._locked():
            if not source.exists():
                return self.get(safe)
            job = self._load_path(source)
            if job.kind is not JobKind.PLAN:
                raise JobQueueError("only PLAN jobs may be delegated")
            job.status = JobStatus.DELEGATED
            job.result = {
                **dict(job.result or {}),
                "delegation": dict(delegation),
            }
            job.error = None
            job.retry_after = None
            job.lease_id = None
            job.worker_id = None
            job.heartbeat_at = None
            job.lease_expires_at = None
            job.updated_at = utc_now()
            self._write(source, job)
            destination = self.delegated / source.name
            source.replace(destination)
            return job

    def restore_delegated(
        self,
        job_id: str,
        *,
        error: str,
        payload_updates: dict[str, Any] | None = None,
    ) -> CoderJob:
        safe = self._safe_id(job_id)
        source = self.delegated / f"{safe}.json"
        with self._locked():
            if not source.exists():
                return self.get(safe)
            job = self._load_path(source)
            job.status = JobStatus.PENDING
            job.error = str(error)[:4000]
            if payload_updates:
                job.payload = {
                    **dict(job.payload or {}),
                    **dict(payload_updates),
                }
            job.result = {}
            job.updated_at = utc_now()
            self._write(source, job)
            destination = self.pending / source.name
            source.replace(destination)
            return job

    def restore_failed_plan_for_local_fallback(
        self,
        job_id: str,
        *,
        error: str,
        reason: str = "provider_unavailable",
    ) -> CoderJob:
        safe = self._safe_id(job_id)
        source = self.failed / f"{safe}.json"
        with self._locked():
            if not source.exists():
                return self.get(safe)
            job = self._load_path(source)
            if job.kind is not JobKind.PLAN:
                raise JobQueueError(
                    "only failed PLAN jobs may use local fallback recovery"
                )
            job.status = JobStatus.PENDING
            job.payload = {
                **dict(job.payload or {}),
                "local_fallback_after_hermes": True,
                "hermes_fallback_reason": str(reason or "provider_unavailable"),
            }
            job.result = {}
            job.error = str(error)[:4000]
            job.retry_after = None
            job.lease_id = None
            job.worker_id = None
            job.heartbeat_at = None
            job.lease_expires_at = None
            job.updated_at = utc_now()
            self._write(source, job)
            destination = self.pending / source.name
            source.replace(destination)
            return job

    def finish_delegated(
        self,
        job_id: str,
        *,
        success: bool,
        result: dict[str, Any],
        error: str | None = None,
    ) -> CoderJob:
        safe = self._safe_id(job_id)
        source = self.delegated / f"{safe}.json"
        with self._locked():
            if not source.exists():
                return self.get(safe)
            job = self._load_path(source)
            job.status = (
                JobStatus.COMPLETED if success else JobStatus.FAILED
            )
            job.result = dict(result or {})
            job.error = None if success else str(error or "delegated_plan_failed")[:4000]
            job.updated_at = utc_now()
            self._write(source, job)
            target = self.completed if success else self.failed
            source.replace(target / source.name)
            return job

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
        packet = dict(result or {})
        # Completing an isolated candidate is never equivalent to completing
        # implementation. Only hold_candidate_for_approval may finish this
        # specific queue lane successfully.
        if (
            job.kind is JobKind.IMPLEMENT
            and job.payload.get("execution_mode") == "ISOLATED_CANDIDATE_ONLY"
        ):
            return self.fail(
                job, "isolated_implementation_requires_founder_review",
                result={
                    "candidate_status": "INVALID_DIRECT_COMPLETION",
                    "implementation_verified": False,
                    "task_completed": False,
                    "founder_release_required": True,
                },
            )
        if job.kind is JobKind.VERIFY:
            verification = packet.get("verification")
            verdict = (
                str(verification.get("verdict") or "").upper()
                if isinstance(verification, dict) else ""
            )
            if verdict not in {"PASS", "PASS_WITH_WARNINGS", "TESTS_ONLY"}:
                return self.fail(
                    job, "verification_verdict_not_successful", result=packet,
                )
        return self._finish(
            job,
            status=JobStatus.COMPLETED,
            result=packet,
            error=None,
        )

    def hold_candidate_for_approval(
        self,
        job: CoderJob,
        result: dict[str, Any],
    ) -> CoderJob:
        """Store a verified isolated *proposal*, never completed implementation."""
        packet = dict(result or {})
        if (
            job.kind is not JobKind.IMPLEMENT
            or job.payload.get("execution_mode") != "ISOLATED_CANDIDATE_ONLY"
            or packet.get("candidate_status") != "LOCAL_PROPOSAL_READY"
            or packet.get("candidate_verification_passed") is not True
            or packet.get("implementation_verified") is not False
            or packet.get("task_completed") is not False
            or packet.get("founder_release_required") is not True
            or not packet.get("proposal_sha256")
        ):
            raise JobQueueError("isolated_candidate_approval_evidence_required")
        return self._finish(
            job,
            status=JobStatus.AWAITING_APPROVAL,
            result=packet,
            error=None,
        )

    def record_approved_release(
        self,
        job_id: str,
        *,
        approval_record: str | Path,
        release_record: str | Path,
    ) -> CoderJob:
        """Consume exact founder approval + source commit evidence.

        This is NOT the worker completion API. It is a manually authorised,
        audit-backed transition for one already-released isolated candidate.
        Failure is read-only, including for spoofed or mismatched receipts.
        """
        safe = self._safe_id(job_id)
        approvals = (
            self.workspace / "runtime/execution_plane/coder_proposals"
        ).resolve()
        paths = (Path(approval_record), Path(release_record))
        for path in paths:
            if (
                path.is_symlink() or not path.is_file()
                or path.resolve().parent != approvals
                or not path.name.startswith(safe + "_")
                or path.suffix != ".json"
            ):
                raise JobQueueError("release_evidence_path_not_authorized")
        try:
            approved = json.loads(paths[0].read_text(encoding="utf-8"))
            release = json.loads(paths[1].read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError) as exc:
            raise JobQueueError("release_evidence_unreadable") from exc
        with self._locked():
            approved_job = self.awaiting_approval / f"{safe}.json"
            recorded = self.released / f"{safe}.json"
            if recorded.is_file():
                prior = self._load_path(recorded)
                if (
                    prior.status is JobStatus.RELEASED
                    and prior.result.get("release", {}).get("release_commit")
                    == release.get("release_commit")
                    and prior.result.get("release", {}).get("approved_patch_sha256")
                    == release.get("approved_patch_sha256")
                ):
                    return prior
                raise JobQueueError("release_reconciliation_conflict")
            if not approved_job.is_file():
                raise JobQueueError("candidate_not_awaiting_approval")
            job = self._load_path(approved_job)
            if (
                job.kind is not JobKind.IMPLEMENT
                or job.status is not JobStatus.AWAITING_APPROVAL
                or job.payload.get("execution_mode") != "ISOLATED_CANDIDATE_ONLY"
                or job.result.get("candidate_status") != "LOCAL_PROPOSAL_READY"
                or job.result.get("candidate_verification_passed") is not True
                or job.result.get("founder_release_required") is not True
            ):
                raise JobQueueError("candidate_release_state_invalid")
            expected_paths = job.payload.get("allowed_paths") or []
            expected_base = job.result.get("source_commit")
            expected_sha = job.result.get("proposal_sha256")
            if (
                not isinstance(expected_paths, list) or not expected_paths
                or not isinstance(expected_sha, str)
                or not re.fullmatch(r"[a-f0-9]{64}", expected_sha)
                or not isinstance(expected_base, str)
                or not re.fullmatch(r"[a-f0-9]{40}", expected_base)
            ):
                raise JobQueueError("original_candidate_provenance_invalid")
            if (
                approved.get("schema_version")
                != "empire.coder.founder_scoped_release_authorization.v1"
                or approved.get("authorization_interpretation")
                != "FOUNDER_APPROVAL_TO_GUARDED_RELEASE_THIS_EXACT_CODE_PATCH_ONLY"
                or approved.get("preflight_approved") is not True
                or approved.get("job_id") != safe
                or approved.get("source_commit") != expected_base
                or approved.get("patch_sha256") != expected_sha
                or approved.get("exact_allowed_paths") != expected_paths
                or release.get("schema_version")
                != "empire.coder.guarded_source_release.v1"
                or release.get("job_id") != safe
                or release.get("approval_record_path") != str(paths[0])
                or release.get("base_commit") != expected_base
                or release.get("approved_patch_sha256") != expected_sha
                or release.get("changed_paths") != expected_paths
                or release.get("source_release_committed") is not True
                or release.get("scoped_release_tests_passed") is not True
            ):
                raise JobQueueError("release_evidence_approval_mismatch")
            commit = release.get("release_commit")
            if not isinstance(commit, str) or not re.fullmatch(
                r"[a-f0-9]{40}", commit
            ):
                raise JobQueueError("release_commit_invalid")
            patch = Path(str(job.result.get("proposal_patch") or ""))
            if (
                not patch.is_file() or patch.is_symlink()
                or patch.resolve().parent != approvals
                or hashlib.sha256(patch.read_bytes()).hexdigest()
                != expected_sha
            ):
                raise JobQueueError("approved_patch_digest_not_verified")

            def git(*args: str, input_bytes: bytes | None = None):
                try:
                    return subprocess.run(
                        ("git", *args), cwd=self.workspace,
                        input=input_bytes, capture_output=True,
                        check=False, timeout=20,
                    )
                except (OSError, subprocess.TimeoutExpired) as exc:
                    raise JobQueueError("release_git_verification_failed") from exc

            ancestor = git("merge-base", "--is-ancestor", commit, "HEAD")
            delta = git("diff-tree", "--no-commit-id", "--name-only", "-r", commit)
            actual_paths = (
                delta.stdout.decode("utf-8", errors="replace").splitlines()
            )
            reversed_patch = git(
                "apply", "--reverse", "--check", "-",
                input_bytes=patch.read_bytes(),
            )
            if (
                ancestor.returncode
                or delta.returncode or set(actual_paths) != set(expected_paths)
                or reversed_patch.returncode
            ):
                raise JobQueueError("release_not_identical_to_live_git_source")
            after = release.get("after_sha256")
            if not isinstance(after, dict) or set(after) != set(expected_paths):
                raise JobQueueError("release_source_digests_missing")
            for path in expected_paths:
                source = (self.workspace / path)
                if (
                    not source.is_file() or source.is_symlink()
                    or not source.resolve().is_relative_to(self.workspace)
                    or hashlib.sha256(source.read_bytes()).hexdigest()
                    != after[path]
                ):
                    raise JobQueueError("released_source_changed_since_approval")
            job.status = JobStatus.RELEASED
            job.result["release"] = {
                "status": "FOUNDER_APPROVED_SOURCE_RELEASE_VERIFIED",
                "release_commit": commit,
                "approved_patch_sha256": expected_sha,
                "released_paths": list(expected_paths),
                "release_receipt": str(paths[1]),
                "source_checksums_verified": True,
            }
            job.updated_at = utc_now()
            self._write(approved_job, job)
            approved_job.replace(recorded)
            return job

    def fail(
        self,
        job: CoderJob,
        error: str,
        *,
        result: dict[str, Any] | None = None,
    ) -> CoderJob:
        return self._finish(
            job,
            status=JobStatus.FAILED,
            result=dict(result or {}),
            error=str(error)[:4000],
        )

    def get(self, job_id: str) -> CoderJob:
        safe = self._safe_id(job_id)
        for directory in (
            self.pending,
            self.running,
            self.delegated,
            self.awaiting_approval,
            self.released,
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
                    self.awaiting_approval,
                    self.released,
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
                self.completed if status is JobStatus.COMPLETED
                else self.awaiting_approval
                if status is JobStatus.AWAITING_APPROVAL
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
