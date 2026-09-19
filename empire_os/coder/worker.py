"""Resumable plan/proposal worker for Empire Coder."""
from __future__ import annotations

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
        terms = tuple(job.payload.get("terms") or ())
        symbols = tuple(job.payload.get("symbols") or ())
        budget = int(job.payload.get("budget_chars") or 12000)
        budget_cap = 6000 if job.kind is JobKind.PLAN else 5000
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
                    "Produce an implementation PLAN ONLY for the task. "
                    "Do not emit shell commands, patches, deployment steps, "
                    "credentials, or production actions. Use the supplied "
                    "evidence, identify affected modules, tests, risks and "
                    "approval gates. The result remains a proposal."
                ),
                context,
                max_output_chars=1200,
            )
            return {
                "kind": job.kind.value,
                "stage": proposal.stage.value,
                "candidate_count": len(proposal.candidate_drafts),
                "revision_count": proposal.revision_count,
                "actionable_patch": False,
                "proposal_persisted": True,
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
