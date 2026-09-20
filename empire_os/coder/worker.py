"""Resumable plan, implementation and verification worker for Empire Coder."""
from __future__ import annotations

import sys
from typing import Any

from .jobs import CoderJob, JobKind, LocalJobQueue
from .orchestrator import EmpireCoder


class CoderTaskWorker:
    def __init__(
        self,
        coder: EmpireCoder,
        queue: LocalJobQueue,
        *,
        stale_seconds: int = 1800,
    ) -> None:
        self.coder = coder
        self.queue = queue
        self.stale_seconds = max(60, int(stale_seconds))

    def run_once(self) -> CoderJob | None:
        self.queue.recover_stale(
            stale_seconds=self.stale_seconds,
        )
        job = self.queue.claim_next()
        if job is None:
            return None
        try:
            result = self._process(job)
        except Exception as exc:
            return self.queue.fail(
                job,
                f"{exc.__class__.__name__}:{exc}",
            )
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
        budget_cap = 4500 if job.kind is JobKind.PLAN else 8000
        context = self.coder.build_context(
            task.id,
            terms=terms,
            symbols=symbols,
            budget_chars=max(4000, min(budget, budget_cap)),
        )

        if job.kind is JobKind.PLAN:
            proposal = self.coder.planner_model_draft(
                task.id,
                (
                    "Produce a concise implementation PLAN ONLY for the task. "
                    "Do not emit shell commands, patches, deployment steps, "
                    "credentials, or production actions. Use only supplied "
                    "evidence. Identify affected modules, focused tests, main "
                    "risks and approval gates. The result is advisory and "
                    "non-actionable."
                ),
                context,
                max_output_chars=450,
            )
            return {
                "kind": job.kind.value,
                "stage": proposal.stage.value,
                "candidate_count": len(proposal.candidate_drafts),
                "revision_count": proposal.revision_count,
                "actionable_patch": False,
                "proposal_persisted": True,
            }

        if job.kind is JobKind.IMPLEMENT:
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

            patch_result = self.coder.apply_structured_patch(
                task.id,
                candidate,
            )
            changed_files = (candidate.proposal.target_path,)
            expected_tests = tuple(
                dict.fromkeys(candidate.proposal.expected_tests)
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
                "production_mutation": False,
            }

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
