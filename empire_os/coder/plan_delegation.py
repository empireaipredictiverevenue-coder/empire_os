"""Model-aware delegation of advisory Empire Coder PLAN jobs to Hermes."""
from __future__ import annotations

from pathlib import Path
from typing import Any
import os

from empire_os.coder import EmpireCoder
from empire_os.coder.audit import AuditTrail
from empire_os.coder.jobs import JobKind, LocalJobQueue
from empire_os.coder.memory import ContextMemory
from empire_os.coder.router import ModelRouter
from empire_os.coder.state import LocalTaskStore
from empire_os.execution_plane_dispatcher import (
    ExecutionRequest,
    dispatch_execution_request,
)
from empire_os.hermes_control import (
    DEFAULT_BASE_BRANCH,
    RESULT_PATH_PREFIX,
    control_path_exists,
    fetch_control_refs,
    read_control_json,
)


_LOCAL_PLANNER_ENV_KEYS = frozenset({
    "EMPIRE_CODER_LLAMA_CPP_ENABLED",
    "EMPIRE_CODER_LLAMA_CPP_URL",
    "EMPIRE_CODER_LLAMA_CPP_MODEL",
    "EMPIRE_CODER_LLAMA_CPP_CAPABILITY",
    "EMPIRE_CODER_LLAMA_CPP_ROLES",
    "EMPIRE_CODER_LLAMA_CPP_TIMEOUT_SECONDS",
})


def _load_local_planner_environment(root: Path) -> None:
    path = root / ".env.empire_coder"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in _LOCAL_PLANNER_ENV_KEYS or key in os.environ:
            continue
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value


def _local_planner_capability(coder: EmpireCoder) -> int:
    return max(
        (
            int(profile.capability)
            for profile in coder.router.profiles
            if profile.local and "planner" in profile.roles
        ),
        default=0,
    )


def delegate_oversized_plans(
    repo_root: str | Path,
    *,
    runtime_root: str | Path | None = None,
    max_jobs: int = 3,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    runtime = Path(runtime_root or root / "runtime/coder").resolve()
    _load_local_planner_environment(root)
    coder = EmpireCoder(root, runtime_root=runtime)
    queue = LocalJobQueue(root, runtime_root=runtime)
    local_capability = _local_planner_capability(coder)
    delegated: list[dict[str, Any]] = []
    blocked: list[dict[str, str]] = []
    skipped_local = 0

    for job in queue.list_pending(kind=JobKind.PLAN):
        if len(delegated) >= max(0, int(max_jobs)):
            break
        try:
            task = coder.store.load(job.task_id)
        except (FileNotFoundError, PermissionError, ValueError) as exc:
            blocked.append({
                "job_id": job.id,
                "task_id": job.task_id,
                "reason": f"task_state_unreadable:{type(exc).__name__}",
            })
            continue
        complexity = ModelRouter.complexity(task.objective)
        if complexity <= local_capability:
            skipped_local += 1
            continue
        request_id = f"coder-plan-{job.id}"
        metadata = {
            "worker": "hermes",
            "request_id": request_id,
            "objective_complexity": complexity,
            "local_planner_capability": local_capability,
            "authority": "observe",
        }
        try:
            delegated_job = queue.delegate_pending(
                job.id,
                delegation=metadata,
            )
            if delegated_job.status.value != "DELEGATED":
                continue
            request = ExecutionRequest(
                request_id=request_id,
                capability="backend_code",
                department="engineering",
                objective=(
                    "Produce a concise advisory implementation PLAN ONLY for "
                    "the following EmpireOS task. Do not edit files, emit "
                    "deployment commands, perform production actions, contact "
                    "external parties, mutate databases, move funds, or expand "
                    "authority. Identify affected modules, focused tests, main "
                    "risks, dependencies, and approval gates.\n\nTASK:\n"
                    + task.objective
                ),
                authority="observe",
                risk_class="low",
                source_ref=f"empire_coder:{job.id}",
                base_branch=DEFAULT_BASE_BRANCH,
                evidence_domains=("engineering", "planning", "repository"),
                success_condition=(
                    "Return an advisory non-actionable plan with modules, tests, "
                    "risks, dependencies and gates; perform no repository mutation."
                ),
                priority=job.priority,
                max_runtime_seconds=600,
            )
            dispatch = dispatch_execution_request(root, request)
            if dispatch.get("worker") != "hermes" or dispatch.get("status") not in {
                "QUEUED", "EXISTS"
            }:
                queue.restore_delegated(
                    job.id,
                    error=f"hermes_delegation_not_queued:{dispatch.get('status')}",
                )
                continue
            delegated.append({
                "job_id": job.id,
                "task_id": job.task_id,
                "request_id": request_id,
                "complexity": complexity,
                "dispatch_status": dispatch.get("status"),
            })
        except Exception as exc:
            try:
                queue.restore_delegated(
                    job.id,
                    error=f"delegation_publish_failed:{type(exc).__name__}:{exc}",
                )
            except Exception:
                pass

    return {
        "schema_version": "empire.coder.plan-delegation.v1",
        "local_planner_capability": local_capability,
        "delegated_count": len(delegated),
        "blocked_count": len(blocked),
        "skipped_local_count": skipped_local,
        "delegated": delegated,
        "blocked": blocked,
        "execution_authority": "none",
    }


def reconcile_delegated_plans(
    repo_root: str | Path,
    *,
    runtime_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    runtime = Path(runtime_root or root / "runtime/coder").resolve()
    queue = LocalJobQueue(root, runtime_root=runtime)
    store = LocalTaskStore(root, runtime_root=runtime)
    audit = AuditTrail(runtime)
    memory = ContextMemory(store, audit)
    fetch_control_refs(root)

    reconciled: list[dict[str, Any]] = []
    for path in sorted(queue.delegated.glob("*.json")):
        job = queue._load_path(path)
        delegation = dict((job.result or {}).get("delegation") or {})
        request_id = str(delegation.get("request_id") or "").strip()
        if not request_id:
            continue
        result_path = RESULT_PATH_PREFIX + f"{request_id}.json"
        if not control_path_exists(root, result_path):
            continue
        result = read_control_json(root, result_path)
        status = str(result.get("status") or "").strip()
        hermes = result.get("hermes") if isinstance(result.get("hermes"), dict) else {}
        output = str(hermes.get("output_tail") or "").strip()
        if status == "COMPLETED_NO_CHANGES" and output:
            store.save_proposal(job.task_id, {
                "task_id": job.task_id,
                "provider": "hermes_control",
                "model": str(hermes.get("model") or "hermes"),
                "stage": "REFINED",
                "draft": output,
                "candidate_drafts": [output],
                "critique": "",
                "refined": output,
                "revision_count": 1,
                "actionable": False,
                "delegated_request_id": request_id,
            })
            terminal = queue.finish_delegated(
                job.id,
                success=True,
                result={
                    "kind": "PLAN",
                    "stage": "REFINED",
                    "provider": "hermes_control",
                    "request_id": request_id,
                    "proposal_persisted": True,
                    "actionable_patch": False,
                    "production_mutation": False,
                },
            )
            memory.retire(
                job.task_id,
                terminal_state=terminal.status.value,
                job_id=terminal.id,
            )
            reconciled.append({
                "job_id": job.id,
                "request_id": request_id,
                "status": "COMPLETED",
            })
        elif status in {
            "FAILED", "HERMES_FAILED", "LEASE_BLOCKED",
            "VERIFICATION_FAILED", "CANDIDATE_GATE_FAILED",
        }:
            terminal = queue.finish_delegated(
                job.id,
                success=False,
                result={
                    "kind": "PLAN",
                    "provider": "hermes_control",
                    "request_id": request_id,
                    "hermes_status": status,
                    "production_mutation": False,
                },
                error=str(result.get("error") or status),
            )
            memory.retire(
                job.task_id,
                terminal_state=terminal.status.value,
                job_id=terminal.id,
            )
            reconciled.append({
                "job_id": job.id,
                "request_id": request_id,
                "status": "FAILED",
            })

    return {
        "schema_version": "empire.coder.plan-reconciliation.v1",
        "reconciled_count": len(reconciled),
        "reconciled": reconciled,
        "execution_authority": "none",
    }
