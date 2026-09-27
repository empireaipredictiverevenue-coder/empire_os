"""Reconcile builder proposal results into independent verification evidence.

No merge/deploy is performed here. This is a read/verify bridge between builder
results and the promotion gate.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from empire_os.candidate_verification import verify_candidate_branch
from empire_os.hermes_control import (
    DEFAULT_CONTROL_BRANCH,
    DEFAULT_REMOTE,
    read_control_json,
)


def reconcile_hermes_result(
    repo_root: str | Path,
    *,
    job_id: str,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    result = read_control_json(
        root,
        f"jobs/results/{job_id}.json",
        control_branch=DEFAULT_CONTROL_BRANCH,
        remote=DEFAULT_REMOTE,
    )
    proposal_branch = str(result.get("proposal_branch") or "").strip()
    if not proposal_branch:
        return {
            "schema_version": "empire.execution-result-reconcile.v1",
            "job_id": job_id,
            "builder": "hermes",
            "status": "NO_PROPOSAL",
            "verification": None,
            "production_merge": False,
            "production_deploy": False,
            "execution_authority": "none",
        }

    job = read_control_json(
        root,
        f"jobs/inbox/{job_id}.json",
        control_branch=DEFAULT_CONTROL_BRANCH,
        remote=DEFAULT_REMOTE,
    )
    allowed_paths = tuple(
        str(value).strip()
        for value in (job.get("allowed_paths") or [])
        if str(value).strip()
    )
    pytest_targets = tuple(
        str(value).strip()
        for value in (job.get("pytest_targets") or [])
        if str(value).strip()
    )
    verification = verify_candidate_branch(
        root,
        proposal_branch=proposal_branch,
        allowed_paths=allowed_paths,
        pytest_targets=pytest_targets,
    )
    return {
        "schema_version": "empire.execution-result-reconcile.v1",
        "job_id": job_id,
        "builder": "hermes",
        "status": (
            "CANDIDATE_VERIFIED"
            if verification.get("passed") is True
            else "CANDIDATE_VERIFICATION_FAILED"
        ),
        "verification": verification,
        "production_merge": False,
        "production_deploy": False,
        "execution_authority": "none",
    }


def write_reconciliation(
    repo_root: str | Path,
    payload: dict[str, Any],
) -> Path:
    root = Path(repo_root).resolve()
    job_id = str(payload.get("job_id") or "unknown").strip()
    out = root / "runtime/execution_plane/reconciled" / f"{job_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(out)
    return out
