"""Governed dispatcher for the Empire Agent & Tool Execution Plane.

Architecture contract:
docs/AGENT_TOOL_EXECUTION_PLANE_ARCHITECTURE.md

The dispatcher routes only observe/internal_write work. Consequential commercial
actions remain outside this plane.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.agent_execution_plane import (
    ExecutionJob,
    route_execution_job,
)
from empire_os.agent_tool_runtime import (
    agent_reach_health,
    pi_health,
    space_agent_health,
)
from empire_os.coder import EmpireCoder
from empire_os.coder.jobs import JobKind, LocalJobQueue
from empire_os.hermes_control import (
    DEFAULT_BASE_BRANCH,
    SCHEMA_VERSION as HERMES_SCHEMA_VERSION,
    publish_control_job,
)
from empire_os.pi_sandbox_runner import PiSandboxJob, run_pi_sandbox_job


RUNTIME_RELATIVE = Path("runtime/execution_plane")


@dataclass(frozen=True)
class ExecutionRequest:
    request_id: str
    capability: str
    department: str
    objective: str
    authority: str = "observe"
    risk_class: str = "low"
    source_ref: str = ""
    allowed_paths: tuple[str, ...] = ()
    lease_resources: tuple[str, ...] = ()
    evidence_domains: tuple[str, ...] = ()
    success_condition: str = ""
    required_tests: tuple[str, ...] = ()
    priority: int = 50
    max_runtime_seconds: int = 900
    traceparent: str | None = None

    def validate(self) -> None:
        if not self.request_id.strip():
            raise ValueError("request_id required")
        if not self.objective.strip():
            raise ValueError("objective required")
        if len(self.objective) > 20_000:
            raise ValueError("objective too long")
        if self.authority not in {"observe", "internal_write"}:
            raise ValueError("execution plane allows observe/internal_write only")
        if self.risk_class not in {
            "low",
            "medium",
            "high",
            "consequential",
        }:
            raise ValueError("unsupported risk class")
        if self.risk_class == "consequential":
            raise ValueError("consequential work requires domain authority gate")
        if (
            self.authority == "internal_write"
            and self.capability in {
                "backend_code",
                "frontend_code",
                "refactor",
                "tests",
                "documentation",
            }
            and not self.allowed_paths
        ):
            raise ValueError(
                "mutating code work requires allowed_paths"
            )
        if (
            self.authority == "internal_write"
            and self.capability in {
                "backend_code",
                "frontend_code",
                "refactor",
                "tests",
                "documentation",
            }
            and not self.lease_resources
        ):
            raise ValueError(
                "mutating code work requires lease_resources"
            )
        for target in self.required_tests:
            if not target.startswith("tests/") or ".py" not in target:
                raise ValueError("required_tests must be repository pytest targets")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_request(
    root: Path,
    lane: str,
    request: ExecutionRequest,
    *,
    extra: Mapping[str, Any] | None = None,
) -> Path:
    target = root / RUNTIME_RELATIVE / "requests" / lane
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{request.request_id}.json"
    payload = {
        "schema_version": "empire.execution-plane-request.v1",
        "queued_at": _now(),
        "lane": lane,
        "request": request.as_dict(),
        "extra": dict(extra or {}),
        "execution_authority": "none",
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return path


def dispatch_execution_request(
    repo_root: str | Path,
    request: ExecutionRequest,
    *,
    execute_pi: bool = True,
) -> dict[str, Any]:
    request.validate()
    root = Path(repo_root).resolve()
    routing = route_execution_job(
        ExecutionJob(
            job_id=request.request_id,
            capability=request.capability,
            department=request.department,
            risk_class=request.risk_class,
            authority=request.authority,
            source_ref=request.source_ref,
            allowed_paths=request.allowed_paths,
            evidence_domains=request.evidence_domains,
            success_condition=request.success_condition,
            required_tests=request.required_tests,
            traceparent=request.traceparent,
        )
    )

    base = {
        "schema_version": "empire.execution-plane-dispatch.v1",
        "request_id": request.request_id,
        "routed_at": _now(),
        "route": routing.as_dict(),
        "external_send": False,
        "payment_action": False,
        "revenue_recognition": False,
        "production_deploy": False,
        "execution_authority": "none",
    }
    if not routing.eligible or not routing.worker_key:
        return {
            **base,
            "status": "BLOCKED",
            "reason": routing.reason,
        }

    worker = routing.worker_key

    if worker == "hermes":
        payload = {
            "schema_version": HERMES_SCHEMA_VERSION,
            "job_id": request.request_id,
            "kind": "code_task",
            "authority": request.authority,
            "base_branch": DEFAULT_BASE_BRANCH,
            "prompt": request.objective,
            "allowed_paths": list(request.allowed_paths),
            "lease_resources": list(
                request.lease_resources
                or tuple(f"path:{path}" for path in request.allowed_paths)
            ),
            "pytest_targets": list(request.required_tests),
            "max_runtime_seconds": request.max_runtime_seconds,
            "created_at": _now(),
        }
        published = publish_control_job(root, payload)
        return {
            **base,
            "status": "QUEUED" if published["published"] else "EXISTS",
            "worker": "hermes",
            "worker_result": published,
        }

    if worker == "pi":
        health = pi_health()
        if not health.ready:
            queued = _write_request(
                root,
                "pi",
                request,
                extra={"tool_health": health.as_dict()},
            )
            return {
                **base,
                "status": "WAITING_FOR_RUNTIME",
                "worker": "pi",
                "request_path": str(queued),
                "tool_health": health.as_dict(),
            }
        if not execute_pi:
            queued = _write_request(root, "pi", request)
            return {
                **base,
                "status": "QUEUED",
                "worker": "pi",
                "request_path": str(queued),
            }
        result = run_pi_sandbox_job(
            root,
            PiSandboxJob(
                job_id=request.request_id,
                prompt=request.objective,
                allowed_paths=request.allowed_paths,
                pytest_targets=request.required_tests,
                lease_resources=request.lease_resources,
                max_runtime_seconds=request.max_runtime_seconds,
            ),
        )
        return {
            **base,
            "status": result.get("status"),
            "worker": "pi",
            "worker_result": result,
        }

    if worker == "empire_coder":
        runtime = root / "runtime/coder"
        coder = EmpireCoder(root, runtime_root=runtime)
        queue = LocalJobQueue(root, runtime_root=runtime)
        task = coder.create_task(request.objective)
        kind = (
            JobKind.IMPLEMENT
            if request.authority == "internal_write"
            else JobKind.PLAN
        )
        job = queue.enqueue(
            task_id=task.id,
            kind=kind,
            priority=max(0, min(int(request.priority), 100)),
            payload={
                "execution_plane_request_id": request.request_id,
                "source_ref": request.source_ref,
                "terms": [
                    request.department,
                    request.capability,
                ],
                "budget_chars": 8000,
                "execution_authority": "none",
            },
        )
        return {
            **base,
            "status": "QUEUED",
            "worker": "empire_coder",
            "coder_task_id": task.id,
            "coder_job_id": job.id,
            "coder_job_kind": kind.value,
        }

    if worker == "space_agent":
        health = space_agent_health()
        queued = _write_request(
            root,
            "space_agent",
            request,
            extra={"tool_health": health.as_dict()},
        )
        return {
            **base,
            "status": (
                "WORKSPACE_REQUEST_READY"
                if health.ready
                else "WAITING_FOR_RUNTIME"
            ),
            "worker": "space_agent",
            "request_path": str(queued),
            "tool_health": health.as_dict(),
        }

    if worker == "agent_reach":
        health = agent_reach_health(probe=False)
        queued = _write_request(
            root,
            "agent_reach",
            request,
            extra={"tool_health": health},
        )
        return {
            **base,
            "status": (
                "SENSOR_REQUEST_READY"
                if health["tool"]["ready"]
                else "WAITING_FOR_RUNTIME"
            ),
            "worker": "agent_reach",
            "request_path": str(queued),
            "tool_health": health,
            "truth_authority": "none",
        }

    if worker in {"swarm_v6", "needle", "laya"}:
        queued = _write_request(root, worker, request)
        return {
            **base,
            "status": "QUEUED",
            "worker": worker,
            "request_path": str(queued),
        }

    return {
        **base,
        "status": "BLOCKED",
        "reason": "worker_adapter_not_implemented",
        "worker": worker,
    }
