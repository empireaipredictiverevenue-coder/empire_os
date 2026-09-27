"""Governed dispatcher for the EmpireDB closeout engineering wave.

This coordinates existing execution-plane workers only. It does not merge,
deploy, mutate production data, change the canonical backend, or cross founder
gates. Mutating builders operate in their existing isolated proposal worktrees.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Mapping

from empire_os.data_cloud_closeout_wave import closeout_requests
from empire_os.execution_plane_dispatcher import (
    ExecutionRequest,
    dispatch_execution_request,
)


ROOT = Path("/srv/empire_os")
LATEST = ROOT / "runtime/data_cloud/closeout_dispatch_latest.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def dispatch_closeout_wave(
    repo_root: str | Path = ROOT,
    *,
    execute_pi: bool = True,
    max_parallel: int = 4,
    dispatcher: Callable[..., Mapping[str, Any]] = dispatch_execution_request,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    requests = closeout_requests()
    worker_count = max(1, min(int(max_parallel), 4))

    results: list[dict[str, Any]] = []
    hermes_publish_lock = Lock()

    def dispatch_one(request: ExecutionRequest) -> dict[str, Any]:
        try:
            # Hermes jobs are published onto one Git control branch. Serialize
            # only that publication boundary to prevent non-fast-forward races;
            # worker execution remains independently leased and asynchronous.
            if request.capability == "backend_code":
                with hermes_publish_lock:
                    result = dict(
                        dispatcher(
                            root,
                            request,
                            execute_pi=execute_pi,
                        )
                    )
            else:
                result = dict(
                    dispatcher(
                        root,
                        request,
                        execute_pi=execute_pi,
                    )
                )
        except Exception as exc:
            result = {
                "schema_version": "empire.execution-plane-dispatch.v1",
                "request_id": request.request_id,
                "status": "DISPATCH_EXCEPTION",
                "error_class": type(exc).__name__,
                "error_detail": str(exc)[-1000:],
                "execution_authority": "none",
                "production_deploy": False,
            }
        return result

    hermes_requests = [
        request
        for request in requests
        if request.capability == "backend_code"
    ]
    parallel_requests = [
        request
        for request in requests
        if request.capability != "backend_code"
    ]

    for request in hermes_requests:
        results.append(dispatch_one(request))

    if parallel_requests:
        with ThreadPoolExecutor(max_workers=worker_count) as pool:
            futures = {
                pool.submit(dispatch_one, request): request
                for request in parallel_requests
            }
            for future in as_completed(futures):
                results.append(future.result())

    results.sort(key=lambda row: str(row.get("request_id") or ""))
    statuses: dict[str, int] = {}
    for row in results:
        status = str(row.get("status") or "UNKNOWN")
        statuses[status] = statuses.get(status, 0) + 1

    failed = {
        "BLOCKED",
        "DISPATCH_EXCEPTION",
        "FAILED",
        "LEASE_CONFLICT",
    }
    dispatch_failures = [
        row
        for row in results
        if str(row.get("status") or "") in failed
    ]

    payload = {
        "schema_version": "empire.data-cloud-closeout-dispatch.v1",
        "observed_at": _now(),
        "request_count": len(requests),
        "execute_pi": bool(execute_pi),
        "max_parallel": worker_count,
        "hermes_queue_mode": "serial_control_branch_publication",
        "status_counts": dict(sorted(statuses.items())),
        "dispatch_failure_count": len(dispatch_failures),
        "results": results,
        "authority": {
            "repository_proposal_work": True,
            "production_deploy": False,
            "database_mutation": False,
            "canonical_backend_change": False,
            "external_send": False,
            "fund_movement": False,
            "revenue_recognition": False,
            "founder_approval_inferred": False,
            "production_cutover_authority": False,
        },
    }
    _atomic_json(
        root / LATEST.relative_to(ROOT),
        payload,
    )
    return payload
