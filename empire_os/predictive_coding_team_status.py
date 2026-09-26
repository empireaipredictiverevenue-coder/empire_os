"""Read-only coding-team status for Founder Console.

Aggregates the canonical Predictive Cloud coding-team assignments across:
- Hermes governed control-branch jobs/results;
- Pi and Swarm execution-plane request queues;
- Empire Coder durable local jobs.

No worker is started, retried, merged or promoted by this module.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.aider_builder import aider_health
from empire_os.builder_capabilities import builder_capability_snapshot
from empire_os.hermes_control import (
    DEFAULT_CONTROL_BRANCH,
    DEFAULT_REMOTE,
    JOB_PATH_PREFIX,
    RESULT_PATH_PREFIX,
    control_path_exists,
    read_control_json,
)
from empire_os.predictive_coding_team import (
    predictive_cloud_coding_team_requests,
)


SCHEMA_VERSION = "empire.coding_team_status.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _empire_coder_job(
    repo_root: Path,
    request_id: str,
) -> dict[str, Any] | None:
    root = repo_root / "runtime" / "coder" / "jobs"
    for state in ("running", "pending", "completed", "failed"):
        directory = root / state
        if not directory.exists():
            continue
        for path in sorted(directory.glob("coder_job_*.json")):
            row = _read_json(path)
            if not isinstance(row, Mapping):
                continue
            payload = row.get("payload")
            payload = payload if isinstance(payload, Mapping) else {}
            if str(
                payload.get("execution_plane_request_id") or ""
            ) != request_id:
                continue
            return {
                "queue_state": state.upper(),
                "job_id": row.get("id"),
                "task_id": row.get("task_id"),
                "kind": row.get("kind"),
                "status": row.get("status"),
                "attempts": row.get("attempts"),
                "error": row.get("error"),
                "worker_id": row.get("worker_id"),
                "updated_at": row.get("updated_at"),
            }
    return None


def _queued_request(
    repo_root: Path,
    worker: str,
    request_id: str,
) -> dict[str, Any] | None:
    path = (
        repo_root
        / "runtime"
        / "execution_plane"
        / "requests"
        / worker
        / f"{request_id}.json"
    )
    row = _read_json(path)
    if row is None:
        return None
    return {
        "queue_state": "QUEUED",
        "request_path": str(path),
        "queued_at": row.get("queued_at"),
        "lane": row.get("lane"),
    }


def _hermes_state(
    repo_root: Path,
    request_id: str,
    *,
    control_branch: str,
    remote: str,
) -> dict[str, Any]:
    job_path = JOB_PATH_PREFIX + f"{request_id}.json"
    result_path = RESULT_PATH_PREFIX + f"{request_id}.json"

    try:
        if control_path_exists(
            repo_root,
            result_path,
            control_branch=control_branch,
            remote=remote,
        ):
            result = read_control_json(
                repo_root,
                result_path,
                control_branch=control_branch,
                remote=remote,
            )
            return {
                "queue_state": "RESULT_AVAILABLE",
                "job_path": job_path,
                "result_path": result_path,
                "status": result.get("status"),
                "proposal_branch": result.get("proposal_branch"),
                "proposal_commit": result.get("proposal_commit"),
                "changed_paths": list(
                    result.get("changed_paths") or []
                ),
                "verification": result.get("verification"),
                "proposal_gate": result.get("proposal_gate"),
                "error": result.get("error"),
                "finished_at": result.get("finished_at"),
            }

        if control_path_exists(
            repo_root,
            job_path,
            control_branch=control_branch,
            remote=remote,
        ):
            return {
                "queue_state": "QUEUED_OR_RUNNING",
                "job_path": job_path,
                "result_path": result_path,
                "status": "AWAITING_RESULT",
            }
    except Exception as exc:
        return {
            "queue_state": "STATUS_UNAVAILABLE",
            "status": "UNKNOWN",
            "reason": f"{type(exc).__name__}:{exc}",
        }

    return {
        "queue_state": "NOT_OBSERVED",
        "status": "UNKNOWN",
    }


def _route_worker(
    capability: str,
    authority: str,
) -> str:
    if capability == "integration_qa":
        return "swarm_v6"
    if capability == "verification":
        return "empire_coder"
    if capability == "parallel_backend_code" and authority == "observe":
        return "pi"
    if capability == "backend_code":
        return "hermes"
    return "unknown"


def build_predictive_coding_team_status(
    repo_root: str | Path,
    *,
    control_branch: str = DEFAULT_CONTROL_BRANCH,
    remote: str = DEFAULT_REMOTE,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    tasks: list[dict[str, Any]] = []

    for request in predictive_cloud_coding_team_requests():
        worker = _route_worker(
            request.capability,
            request.authority,
        )

        if worker == "hermes":
            state = _hermes_state(
                root,
                request.request_id,
                control_branch=control_branch,
                remote=remote,
            )
        elif worker == "empire_coder":
            state = _empire_coder_job(
                root,
                request.request_id,
            ) or {
                "queue_state": "NOT_OBSERVED",
                "status": "UNKNOWN",
            }
        elif worker in {"pi", "swarm_v6"}:
            state = _queued_request(
                root,
                worker,
                request.request_id,
            ) or {
                "queue_state": "NOT_OBSERVED",
                "status": "UNKNOWN",
            }
        else:
            state = {
                "queue_state": "STATUS_UNAVAILABLE",
                "status": "UNKNOWN",
                "reason": "worker_status_adapter_missing",
            }

        tasks.append({
            "request_id": request.request_id,
            "worker": worker,
            "department": request.department,
            "capability": request.capability,
            "authority": request.authority,
            "priority": request.priority,
            "success_condition": request.success_condition,
            "required_tests": list(request.required_tests),
            "state": state,
            "execution_authority": "none",
        })

    counts: dict[str, int] = {}
    for task in tasks:
        key = str(
            (task.get("state") or {}).get("queue_state")
            or "UNKNOWN"
        )
        counts[key] = counts.get(key, 0) + 1

    blockers = [
        {
            "request_id": task["request_id"],
            "worker": task["worker"],
            "queue_state": task["state"].get("queue_state"),
            "status": task["state"].get("status"),
            "reason": (
                task["state"].get("reason")
                or task["state"].get("error")
            ),
        }
        for task in tasks
        if (
            task["state"].get("queue_state")
            in {"FAILED", "STATUS_UNAVAILABLE", "NOT_OBSERVED"}
            or str(task["state"].get("status") or "").upper()
            in {
                "FAILED",
                "HERMES_FAILED",
                "VERIFICATION_FAILED",
                "CANDIDATE_GATE_FAILED",
            }
        )
    ]

    capabilities = builder_capability_snapshot(
        root / "runtime/execution_plane/builder_capabilities.json"
    )
    empire_coder_caps = (
        (capabilities.get("workers") or {}).get("empire_coder") or {}
    )
    coder_backends = {
        "native_structured_patch": {
            "capability": empire_coder_caps.get(
                "structured_patch_mutation"
            ),
        },
        "aider": {
            "health": aider_health(),
            "capability": empire_coder_caps.get("aider_mutation"),
        },
        "openhands": {
            "workspace_contract_ready": True,
            "capability": empire_coder_caps.get(
                "openhands_workspace"
            ),
            "mutation_capability_proven": False,
        },
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "observed_at": _now(),
        "team": "predictive_cloud_agi_quantum",
        "task_count": len(tasks),
        "state_counts": dict(sorted(counts.items())),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "tasks": tasks,
        "coder_backends": coder_backends,
        "read_only": True,
        "remote_fetch_performed": False,
        "worker_started": False,
        "merge_performed": False,
        "production_deploy": False,
        "external_execution_performed": False,
        "execution_authority": "none",
    }
