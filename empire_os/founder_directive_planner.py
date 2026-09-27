"""Automatic planning coordinator for captured Founder Directives."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from empire_os.coder import EmpireCoder
from empire_os.coder.jobs import JobKind, JobStatus, LocalJobQueue
from empire_os.founder_directives import FounderDirectiveStore


def _plan_objective(text: str, authority: str, gate_reasons: tuple[str, ...]) -> str:
    gate = (
        " Founder-gate reasons: " + ", ".join(gate_reasons) + "."
        if gate_reasons else ""
    )
    return (
        "PLAN ONLY: integrate this Founder Directive into the existing EmpireOS "
        "business rather than creating a disconnected duplicate. First search the "
        "repo/docs/runtime contracts for existing relevant modules. Produce a "
        "refined plan covering: reuse vs new work, architecture placement, data "
        "contracts, automation path, acceptance tests, observability/Daily Results, "
        "deployment sequence, rollback, commercial impact, and authority gates. "
        "Unknown facts must remain unknown. Do not execute production mutations, "
        "send outbound, accept terms, move funds, or recognize revenue. "
        f"Directive authority={authority}.{gate} Directive: {text}"
    )


def plan_captured_directives(
    repo_root: str | Path,
    *,
    limit: int = 5,
    coder_factory: Callable[..., Any] = EmpireCoder,
    queue_factory: Callable[..., Any] = LocalJobQueue,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    store = FounderDirectiveStore(root)
    coder_root = root / "runtime" / "coder"
    coder = coder_factory(root, runtime_root=coder_root)
    queue = queue_factory(root, runtime_root=coder_root)

    # Reconcile previously queued plans first.
    reconciled = 0
    failures = 0
    for row in store.list(statuses={"planning"}):
        if not row.coder_job_id:
            continue
        try:
            job = queue.get(row.coder_job_id)
        except Exception:
            continue
        if job.status is JobStatus.COMPLETED:
            next_status = (
                "founder_gate"
                if row.authority == "founder_gate"
                else "implementation_ready"
            )
            store.update(
                row.id,
                status=next_status,
                plan_result=dict(job.result or {}),
            )
            reconciled += 1
        elif job.status is JobStatus.FAILED:
            store.update(
                row.id,
                status="plan_failed",
                plan_result={
                    "error": str(job.error or "plan_failed")[:2000]
                },
            )
            failures += 1

    queued = 0
    for row in store.list(statuses={"captured", "plan_failed"})[:max(1, min(int(limit), 20))]:
        task = coder.create_task(
            _plan_objective(
                row.text,
                row.authority,
                row.gate_reasons,
            )
        )
        job = queue.enqueue(
            task_id=task.id,
            kind=JobKind.PLAN,
            priority=row.priority,
            payload={
                "terms": [
                    row.category,
                    "founder",
                    "directive",
                    "architecture",
                    "automation",
                    "daily_results",
                ],
                "budget_chars": 5600,
                "directive_id": row.id,
                "authority": row.authority,
            },
        )
        store.update(
            row.id,
            status="planning",
            coder_task_id=task.id,
            coder_job_id=job.id,
            plan_result={},
        )
        queued += 1

    snapshot = store.summary()
    return {
        "ok": True,
        "queued": queued,
        "reconciled": reconciled,
        "plan_failures": failures,
        "directive_count": snapshot["directive_count"],
        "status_counts": snapshot["status_counts"],
        "founder_gate_count": snapshot["founder_gate_count"],
        "automatic_production_execution": False,
        "execution_mode": "OBSERVE",
    }
