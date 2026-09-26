"""Resumable plan, implementation and verification worker for Empire Coder."""
from __future__ import annotations

import os
import sys
import threading
from typing import Any

from empire_os.execution_lease import (
    ExecutionLeaseError,
    ExecutionLeaseManager,
)

from .jobs import CoderJob, JobKind, LocalJobQueue
from .orchestrator import EmpireCoder


def _path_allowed(path: str, allowed: tuple[str, ...]) -> bool:
    clean = str(path or "").strip().replace("\\", "/").lstrip("./")
    for raw in allowed:
        prefix = str(raw or "").strip().replace("\\", "/").lstrip("./").rstrip("/")
        if prefix and (clean == prefix or clean.startswith(prefix + "/")):
            return True
    return False


class CoderTaskWorker:
    def __init__(
        self,
        coder: EmpireCoder,
        queue: LocalJobQueue,
        *,
        stale_seconds: int = 240,
        lease_seconds: int = 240,
        heartbeat_seconds: int = 30,
        max_attempts: int = 3,
        execution_lease_manager: ExecutionLeaseManager | None = None,
    ) -> None:
        self.coder = coder
        self.queue = queue
        self.stale_seconds = max(60, int(stale_seconds))
        self.lease_seconds = max(60, int(lease_seconds))
        self.heartbeat_seconds = max(10, int(heartbeat_seconds))
        self.max_attempts = max(1, int(max_attempts))
        self.execution_leases = execution_lease_manager

    def _execution_lease_manager(self) -> ExecutionLeaseManager:
        """Resolve the default mutation lease manager only when required.

        PLAN/retry-only workers do not need a workspace-backed mutation lease.
        Mutation paths still require a real queue workspace unless an explicit
        lease manager was injected.
        """
        if self.execution_leases is not None:
            return self.execution_leases

        workspace = getattr(self.queue, "workspace", None)
        if workspace is None:
            raise RuntimeError(
                "workspace-backed execution lease manager required "
                "for mutation jobs"
            )

        self.execution_leases = ExecutionLeaseManager(
            workspace / "runtime/execution_plane"
        )
        return self.execution_leases

    @staticmethod
    def _transient_error(exc: Exception) -> bool:
        text = f"{exc.__class__.__name__}:{exc}".lower()
        return any(
            token in text
            for token in (
                "timeout",
                "temporarily unavailable",
                "connection reset",
                "connection refused",
                "ollama_request_failed",
                "service unavailable",
            )
        )

    def _heartbeat_loop(
        self,
        job: CoderJob,
        stop: threading.Event,
    ) -> None:
        while not stop.wait(self.heartbeat_seconds):
            try:
                self.queue.heartbeat(
                    job,
                    lease_seconds=self.lease_seconds,
                )
            except Exception:
                return

    def run_once(self) -> CoderJob | None:
        self.queue.recover_stale(
            stale_seconds=self.stale_seconds,
            max_attempts=self.max_attempts,
        )
        self.queue.quarantine_exhausted(
            max_attempts=self.max_attempts,
        )
        job = self.queue.claim_next(
            worker_id=f"pid:{os.getpid()}",
            lease_seconds=self.lease_seconds,
        )
        if job is None:
            return None

        stop = threading.Event()
        heartbeat = threading.Thread(
            target=self._heartbeat_loop,
            args=(job, stop),
            daemon=True,
            name=f"coder-heartbeat-{job.id[-8:]}",
        )
        heartbeat.start()
        try:
            result = self._process(job)
        except Exception as exc:
            stop.set()
            heartbeat.join(timeout=2)
            error = f"{exc.__class__.__name__}:{exc}"
            if self._transient_error(exc):
                if job.attempts >= self.max_attempts:
                    return self.queue.fail(
                        job,
                        f"{error}:max_attempts_exhausted",
                    )
                delay = min(300, 30 * (2 ** max(0, job.attempts - 1)))
                return self.queue.retry(
                    job,
                    error,
                    delay_seconds=delay,
                    max_attempts=self.max_attempts,
                )
            return self.queue.fail(job, error)

        stop.set()
        heartbeat.join(timeout=2)
        return self.queue.complete(job, result)

    def _process(self, job: CoderJob) -> dict[str, Any]:
        task = self.coder.load_task(job.task_id)

        if job.kind is JobKind.VERIFY:
            changed_files = tuple(
                str(value).strip()
                for value in (job.payload.get("changed_files") or ())
                if str(value).strip()
            )
            tests = tuple(
                str(value).strip()
                for value in (job.payload.get("tests") or ())
                if str(value).strip()
            )
            if not changed_files:
                raise ValueError("VERIFY requires changed_files")
            if any(
                not test.startswith("tests/") or not test.endswith(".py")
                for test in tests
            ):
                raise ValueError("VERIFY tests must be repository test files")
            commands = (
                ((sys.executable, "-m", "pytest", "-q", *tests),)
                if tests
                else ()
            )
            verification = self.coder.verify(
                task.id,
                changed_files=changed_files,
                commands=commands,
            )
            return {
                "kind": job.kind.value,
                "changed_files": list(changed_files),
                "tests": list(tests),
                "verification": verification.as_dict(),
                "model_inference": False,
                "production_mutation": False,
            }

        terms = tuple(job.payload.get("terms") or ())
        symbols = tuple(job.payload.get("symbols") or ())
        budget = int(job.payload.get("budget_chars") or 12000)
        budget_cap = 5600 if job.kind is JobKind.PLAN else 8000
        context = self.coder.build_context(
            task.id,
            terms=terms,
            symbols=symbols,
            budget_chars=max(4000, min(budget, budget_cap)),
        )

        if job.kind is JobKind.PLAN:
            proposal = self.coder.polished_model_output(
                task.id,
                (
                    "Produce a concise implementation PLAN ONLY for the task. "
                    "Do not emit shell commands, patches, deployment steps, "
                    "credentials, or production actions. Use only supplied "
                    "evidence. Identify affected modules, focused tests, main "
                    "risks and approval gates. Critique the first proposal and "
                    "return a refined advisory plan. The result remains "
                    "non-actionable regardless of model output."
                ),
                context,
                max_output_chars=1800,
                role="planner",
            )
            return {
                "kind": job.kind.value,
                "stage": proposal.stage.value,
                "candidate_count": len(proposal.candidate_drafts),
                "revision_count": proposal.revision_count,
                "refined": bool(str(proposal.refined or "").strip()),
                "actionable_patch": False,
                "proposal_persisted": True,
                "production_mutation": False,
            }

        if job.kind is JobKind.IMPLEMENT:
            execution_request_id = str(
                job.payload.get("execution_plane_request_id") or ""
            ).strip()
            allowed_paths = tuple(
                str(value).strip()
                for value in (job.payload.get("allowed_paths") or ())
                if str(value).strip()
            )
            lease_resources = tuple(
                str(value).strip()
                for value in (job.payload.get("lease_resources") or ())
                if str(value).strip()
            )
            required_tests = tuple(
                str(value).strip()
                for value in (job.payload.get("required_tests") or ())
                if str(value).strip()
            )
            if execution_request_id and (
                not allowed_paths or not lease_resources
            ):
                raise ValueError(
                    "execution-plane IMPLEMENT requires allowed_paths "
                    "and lease_resources"
                )

            candidate = self.coder.propose_structured_patch(
                task.id,
                (
                    "Implement the smallest safe DEVELOPMENT patch for the "
                    "task objective using only supplied repository evidence. "
                    "Do not touch protected paths, deployment, services, "
                    "production databases, outbound systems, credentials, "
                    "or funds. Prefer one narrow code change with focused "
                    "tests. The patch must remain inside the repository and "
                    "must be verifiable before any commit."
                ),
                context,
            )
            if not candidate.eligible:
                return {
                    "kind": job.kind.value,
                    "eligible": False,
                    "applied": False,
                    "validation_reasons": list(
                        candidate.validation.reasons
                    ),
                    "validation_warnings": list(
                        candidate.validation.warnings
                    ),
                }

            if allowed_paths and not _path_allowed(
                candidate.proposal.target_path,
                allowed_paths,
            ):
                return {
                    "kind": job.kind.value,
                    "eligible": False,
                    "applied": False,
                    "validation_reasons": [
                        "execution_plane_path_policy_failed"
                    ],
                    "target_path": candidate.proposal.target_path,
                }

            lease = None
            try:
                if lease_resources:
                    lease = self._execution_lease_manager().acquire(
                        owner="empire_coder",
                        job_id=execution_request_id or job.id,
                        resources=lease_resources,
                        ttl_seconds=max(
                            300,
                            int(job.payload.get("lease_seconds") or 1200),
                        ),
                    )

                patch_result = self.coder.apply_structured_patch(
                    task.id,
                    candidate,
                )
                changed_files = (candidate.proposal.target_path,)
                expected_tests = tuple(
                    dict.fromkeys(
                        candidate.proposal.expected_tests
                        + required_tests
                    )
                )
                impacted_tests = tuple(
                    self.coder.impacted_tests(changed_files)
                )
                tests = tuple(
                    dict.fromkeys(expected_tests + impacted_tests)
                )
                commands = (
                    (("pytest", "-q", *tests),)
                    if tests
                    else ()
                )
                verification = self.coder.verify(
                    task.id,
                    changed_files=changed_files,
                    commands=commands,
                )
                return {
                    "kind": job.kind.value,
                    "eligible": True,
                    "applied": True,
                    "target_path": candidate.proposal.target_path,
                    "operation": candidate.proposal.operation.value,
                    "patch_result": patch_result,
                    "tests": list(tests),
                    "verification": verification.as_dict(),
                    "candidate_commit_required": True,
                    "execution_plane_request_id": execution_request_id or None,
                    "lease_id": lease.lease_id if lease else None,
                    "production_mutation": False,
                }
            except ExecutionLeaseError as exc:
                return {
                    "kind": job.kind.value,
                    "eligible": False,
                    "applied": False,
                    "validation_reasons": [
                        f"execution_lease_blocked:{exc}"
                    ],
                }
            finally:
                if lease is not None:
                    try:
                        self._execution_lease_manager().release(lease.lease_id)
                    except Exception:
                        pass

        if job.kind is JobKind.NEXT_COMMAND:
            proposal = self.coder.propose_next_command(
                task.id,
                (
                    "Choose the safest next DEVELOPMENT VERIFICATION command "
                    "for the current task state. Do not propose mutation, "
                    "deployment, network, service-control or production work."
                ),
                context,
            )
            return {
                "kind": job.kind.value,
                "candidate_count": len(proposal.candidate_texts),
                "argv": list(proposal.argv),
                "policy_decision": proposal.decision.value,
                "eligible": proposal.eligible,
                "executed": False,
            }

        raise ValueError(f"unsupported job kind: {job.kind.value}")
