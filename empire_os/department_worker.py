"""Safe worker for Astra department work.

Only explicit internal adapters may execute. Unsupported targets are blocked
with evidence rather than being treated as complete.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
from typing import Any

from empire_os.coder import EmpireCoder
from empire_os.coder.jobs import JobKind, LocalJobQueue
from empire_os.department_work_queue import DepartmentWorkQueue


SAFE_COMMANDS = {
    "commercial_product_catalog": (
        "scripts/refresh_commercial_product_catalog.py",
        "runtime:commercial_product_catalog",
    ),
    "buyer_capacity_readiness": (
        "scripts/build_buyer_capacity_readiness.py",
        "runtime:buyer_capacity_readiness",
    ),
    "predictive_cloud_opportunity_loop": (
        "scripts/run_opportunity_loop.py",
        "runtime:opportunity_radar:loop_latest",
    ),
    "predictive_cloud_status": (
        "scripts/build_predictive_cloud_status.py",
        "runtime:predictive_cloud:status_latest",
    ),
}


def _coder_bridge(repo_root: Path, item: Any) -> dict[str, Any]:
    runtime_root = repo_root / "runtime" / "coder"
    coder = EmpireCoder(repo_root, runtime_root=runtime_root)
    queue = LocalJobQueue(repo_root, runtime_root=runtime_root)
    objective = (
        "Department work delegated by Astra Executive. "
        f"Goal={item.goal_key}; department_keys={list(item.department_keys)}; "
        f"action={item.action}; target_component={item.target_component}; "
        f"rationale={item.rationale}; success_condition="
        f"{item.success_condition}; evidence_refs={list(item.evidence_refs)}. "
        "PLAN ONLY unless the governed Empire Coder pipeline separately "
        "promotes implementation. Do not perform external communication, "
        "move funds, accept commercial terms, recognize revenue or expand "
        "authority."
    )
    task = coder.create_task(objective)
    job = queue.enqueue(
        task_id=task.id,
        kind=JobKind.PLAN,
        priority=item.priority,
        payload={
            "department_work_id": item.id,
            "astra_plan_id": item.plan_id,
            "astra_step_id": item.step_id,
            "execution_authority": "none",
            "terms": [
                *item.department_keys,
                item.target_component,
                item.action,
            ],
            "budget_chars": 7000,
        },
    )
    return {
        "adapter": "empire_coder_plan_bridge",
        "coder_task_id": task.id,
        "coder_job_id": job.id,
        "implementation_performed": False,
        "external_execution_performed": False,
        "execution_authority": "none",
    }


def run_one_department_work(
    repo_root: str | Path,
    *,
    worker_id: str = "department-worker",
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    queue = DepartmentWorkQueue(root)
    queue.recover_stale()
    item = queue.claim_next(
        worker_id=worker_id,
        lease_seconds=max(180, timeout_seconds + 60),
    )
    if item is None:
        return {
            "ok": True,
            "state": "IDLE",
            "work_processed": False,
            "queue_counts": queue.counts(),
            "execution_authority": "none",
        }

    if item.authority not in {"observe", "internal_write"}:
        blocked = queue.block(
            item,
            "authority_not_safe_for_department_worker",
        )
        return {
            "ok": True,
            "state": "BLOCKED",
            "work_id": blocked.id,
            "blocker": blocked.error,
            "queue_counts": queue.counts(),
            "execution_authority": "none",
        }

    if item.target_component == "empire_coder":
        try:
            result = _coder_bridge(root, item)
            done = queue.complete(
                item,
                result,
                evidence_refs=(
                    f"coder_task:{result['coder_task_id']}",
                    f"coder_job:{result['coder_job_id']}",
                ),
            )
            return {
                "ok": True,
                "state": "DONE",
                "work_id": done.id,
                "target_component": done.target_component,
                "result": done.result,
                "queue_counts": queue.counts(),
                "execution_authority": "none",
            }
        except Exception as exc:
            failed = queue.fail(item, str(exc))
            return {
                "ok": False,
                "state": "FAILED",
                "work_id": failed.id,
                "error": failed.error,
                "queue_counts": queue.counts(),
                "execution_authority": "none",
            }

    adapter = SAFE_COMMANDS.get(item.target_component)
    if adapter is None:
        blocked = queue.block(
            item,
            "specialist_adapter_required",
            {
                "target_component": item.target_component,
                "action": item.action,
                "required_department_keys": list(item.department_keys),
                "intelligence_request": item.intelligence_request,
                "external_execution_performed": False,
            },
        )
        return {
            "ok": True,
            "state": "BLOCKED",
            "work_id": blocked.id,
            "target_component": blocked.target_component,
            "blocker": blocked.error,
            "queue_counts": queue.counts(),
            "execution_authority": "none",
        }

    script, evidence_ref = adapter
    command = [
        str(root / ".venv" / "bin" / "python"),
        str(root / script),
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)

    try:
        completed = subprocess.run(
            command,
            cwd=str(root),
            env=env,
            capture_output=True,
            text=True,
            timeout=max(10, min(int(timeout_seconds), 600)),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        failed = queue.fail(
            item,
            f"adapter_timeout:{item.target_component}:{exc.timeout}",
        )
        return {
            "ok": False,
            "state": "FAILED",
            "work_id": failed.id,
            "error": failed.error,
            "queue_counts": queue.counts(),
            "execution_authority": "none",
        }

    result = {
        "adapter": "safe_internal_command",
        "target_component": item.target_component,
        "command_script": script,
        "returncode": completed.returncode,
        "stdout_tail": (completed.stdout or "")[-4000:],
        "stderr_tail": (completed.stderr or "")[-4000:],
        "external_execution_performed": False,
        "commercial_authority": "none",
        "execution_authority": "none",
    }
    if completed.returncode != 0:
        failed = queue.fail(
            item,
            f"adapter_exit_{completed.returncode}",
        )
        return {
            "ok": False,
            "state": "FAILED",
            "work_id": failed.id,
            "result": result,
            "queue_counts": queue.counts(),
            "execution_authority": "none",
        }

    done = queue.complete(
        item,
        result,
        evidence_refs=(evidence_ref,),
    )
    return {
        "ok": True,
        "state": "DONE",
        "work_id": done.id,
        "target_component": done.target_component,
        "result_evidence_refs": list(done.result_evidence_refs),
        "queue_counts": queue.counts(),
        "execution_authority": "none",
    }


def run_department_worker(
    repo_root: str | Path,
    *,
    max_items: int = 4,
    worker_id: str = "department-worker",
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    bounded = max(1, min(int(max_items), 20))
    results: list[dict[str, Any]] = []
    for _ in range(bounded):
        result = run_one_department_work(
            repo_root,
            worker_id=worker_id,
            timeout_seconds=timeout_seconds,
        )
        results.append(result)
        if result.get("state") == "IDLE":
            break
    return {
        "ok": all(row.get("ok") is not False for row in results),
        "processed_count": sum(
            row.get("state") not in {None, "IDLE"}
            for row in results
        ),
        "done_count": sum(row.get("state") == "DONE" for row in results),
        "blocked_count": sum(
            row.get("state") == "BLOCKED" for row in results
        ),
        "failed_count": sum(
            row.get("state") == "FAILED" for row in results
        ),
        "results": results,
        "external_execution_performed": False,
        "execution_authority": "none",
    }
