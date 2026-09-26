"""Fail-closed internal API for Empire Coder task orchestration."""
from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from .jobs import JobKind, JobQueueError, LocalJobQueue
from .orchestrator import EmpireCoder
from .state import TaskStateError, compact_task_context


router = APIRouter(prefix="/v1/coder", tags=["empire-coder"])


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _api_enabled() -> bool:
    return _truthy(os.getenv("EMPIRE_CODER_API_ENABLED", "0"))


def _workspace() -> Path:
    return Path(
        os.getenv("EMPIRE_CODER_WORKSPACE", "/srv/empire_os")
    ).expanduser()


def _runtime_root() -> str | None:
    value = os.getenv("EMPIRE_CODER_RUNTIME_ROOT", "").strip()
    return value or None


def _require_internal(
    x_empire_coder_token: str | None = Header(
        default=None,
        alias="X-Empire-Coder-Token",
    ),
) -> None:
    if not _api_enabled():
        raise HTTPException(
            status_code=503,
            detail="empire_coder_api_disabled",
        )
    expected = os.getenv(
        "EMPIRE_CODER_API_INTERNAL_TOKEN", ""
    ).strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="empire_coder_internal_token_not_configured",
        )
    supplied = str(x_empire_coder_token or "")
    if not secrets.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=401,
            detail="empire_coder_internal_auth_failed",
        )


def _coder() -> EmpireCoder:
    try:
        return EmpireCoder(
            _workspace(),
            runtime_root=_runtime_root(),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="empire_coder_runtime_unavailable",
        ) from exc


def _queue() -> LocalJobQueue:
    try:
        return LocalJobQueue(
            _workspace(),
            runtime_root=_runtime_root(),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="empire_coder_queue_unavailable",
        ) from exc


class TaskCreateRequest(BaseModel):
    objective: str = Field(min_length=3, max_length=10_000)
    blueprint_path: str = Field(
        default="docs/BLUEPRINT_V6.md",
        min_length=5,
        max_length=300,
    )


class JobRequest(BaseModel):
    terms: list[str] = Field(default_factory=list, max_length=20)
    symbols: list[str] = Field(default_factory=list, max_length=20)
    budget_chars: int = Field(default=12_000, ge=4_000, le=24_000)


def _validate_blueprint_path(path: str) -> str:
    candidate = str(path).strip()
    parts = Path(candidate).parts
    if (
        not candidate.startswith("docs/")
        or Path(candidate).is_absolute()
        or ".." in parts
    ):
        raise HTTPException(
            status_code=400,
            detail="blueprint_path_must_be_relative_docs_path",
        )
    return candidate


def _task_or_404(coder: EmpireCoder, task_id: str):
    try:
        return coder.load_task(task_id)
    except TaskStateError as exc:
        raise HTTPException(
            status_code=404,
            detail="coder_task_not_found",
        ) from exc


@router.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "api_enabled": _api_enabled(),
        "execution_mode": "OBSERVE",
        "production_authority": False,
        "command_execution_endpoint": False,
        "patch_execution_endpoint": False,
        "job_types": [
            JobKind.PLAN.value,
            JobKind.NEXT_COMMAND.value,
        ],
    }


@router.post("/tasks")
def create_task(
    req: TaskCreateRequest,
    x_empire_coder_token: str | None = Header(
        default=None,
        alias="X-Empire-Coder-Token",
    ),
):
    _require_internal(x_empire_coder_token)
    coder = _coder()
    task = coder.create_task(
        req.objective,
        blueprint_path=_validate_blueprint_path(
            req.blueprint_path
        ),
    )
    return {
        "task_id": task.id,
        "status": task.status.value,
        "phase": task.phase.value,
        "execution_mode": "OBSERVE",
        "production_authority": False,
    }


@router.get("/tasks/{task_id}")
def task_status(
    task_id: str,
    x_empire_coder_token: str | None = Header(
        default=None,
        alias="X-Empire-Coder-Token",
    ),
):
    _require_internal(x_empire_coder_token)
    coder = _coder()
    task = _task_or_404(coder, task_id)
    return compact_task_context(task)


@router.get("/tasks/{task_id}/memory")
def task_memory(
    task_id: str,
    x_empire_coder_token: str | None = Header(
        default=None,
        alias="X-Empire-Coder-Token",
    ),
):
    _require_internal(x_empire_coder_token)
    coder = _coder()
    _task_or_404(coder, task_id)
    snapshot = coder.memory.load(task_id)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="coder_task_memory_not_found",
        )
    return snapshot


def _enqueue(
    *,
    task_id: str,
    kind: JobKind,
    req: JobRequest,
):
    coder = _coder()
    _task_or_404(coder, task_id)
    job = _queue().enqueue(
        task_id=task_id,
        kind=kind,
        payload={
            "terms": list(dict.fromkeys(req.terms)),
            "symbols": list(dict.fromkeys(req.symbols)),
            "budget_chars": req.budget_chars,
        },
    )
    return {
        "job_id": job.id,
        "task_id": job.task_id,
        "kind": job.kind.value,
        "status": job.status.value,
        "executed": False,
    }


@router.post("/tasks/{task_id}/plan")
def enqueue_plan(
    task_id: str,
    req: JobRequest,
    x_empire_coder_token: str | None = Header(
        default=None,
        alias="X-Empire-Coder-Token",
    ),
):
    _require_internal(x_empire_coder_token)
    return _enqueue(
        task_id=task_id,
        kind=JobKind.PLAN,
        req=req,
    )


@router.post("/tasks/{task_id}/next-command")
def enqueue_next_command(
    task_id: str,
    req: JobRequest,
    x_empire_coder_token: str | None = Header(
        default=None,
        alias="X-Empire-Coder-Token",
    ),
):
    _require_internal(x_empire_coder_token)
    return _enqueue(
        task_id=task_id,
        kind=JobKind.NEXT_COMMAND,
        req=req,
    )


@router.get("/jobs/{job_id}")
def job_status(
    job_id: str,
    x_empire_coder_token: str | None = Header(
        default=None,
        alias="X-Empire-Coder-Token",
    ),
):
    _require_internal(x_empire_coder_token)
    try:
        job = _queue().get(job_id)
    except JobQueueError as exc:
        raise HTTPException(
            status_code=404,
            detail="coder_job_not_found",
        ) from exc
    return job.as_dict()


@router.get("/knowledge")
def knowledge_status(
    x_empire_coder_token: str | None = Header(
        default=None,
        alias="X-Empire-Coder-Token",
    ),
):
    _require_internal(x_empire_coder_token)
    return _coder().refresh_knowledge()
