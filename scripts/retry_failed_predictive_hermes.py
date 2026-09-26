#!/usr/bin/env python3
"""Republish failed canonical Hermes coding jobs under deterministic recovery IDs."""
from __future__ import annotations

import json
from pathlib import Path

from empire_os.hermes_control import (
    DEFAULT_CONTROL_BRANCH,
    DEFAULT_REMOTE,
    RESULT_PATH_PREFIX,
    control_path_exists,
    publish_control_job,
    read_control_json,
)
from empire_os.predictive_coding_team import predictive_cloud_coding_team_requests


ROOT = Path("/srv/empire_os")
FAILED = {
    "FAILED",
    "HERMES_FAILED",
    "VERIFICATION_FAILED",
    "CANDIDATE_GATE_FAILED",
    "LEASE_BLOCKED",
}


def _recovery_id(request_id: str) -> str:
    return f"{request_id}-recovery-v1"


def main() -> int:
    rows = []
    for request in predictive_cloud_coding_team_requests():
        if request.capability != "backend_code":
            continue

        original_result_path = (
            RESULT_PATH_PREFIX + f"{request.request_id}.json"
        )
        if not control_path_exists(
            ROOT,
            original_result_path,
            control_branch=DEFAULT_CONTROL_BRANCH,
            remote=DEFAULT_REMOTE,
        ):
            continue

        original = read_control_json(
            ROOT,
            original_result_path,
            control_branch=DEFAULT_CONTROL_BRANCH,
            remote=DEFAULT_REMOTE,
        )
        status = str(original.get("status") or "").upper()
        if status not in FAILED:
            continue

        recovery_id = _recovery_id(request.request_id)
        recovery_result_path = (
            RESULT_PATH_PREFIX + f"{recovery_id}.json"
        )
        if control_path_exists(
            ROOT,
            recovery_result_path,
            control_branch=DEFAULT_CONTROL_BRANCH,
            remote=DEFAULT_REMOTE,
        ):
            recovery = read_control_json(
                ROOT,
                recovery_result_path,
                control_branch=DEFAULT_CONTROL_BRANCH,
                remote=DEFAULT_REMOTE,
            )
            rows.append({
                "request_id": request.request_id,
                "recovery_id": recovery_id,
                "action": "existing_recovery_result",
                "status": recovery.get("status"),
            })
            continue

        payload = {
            "schema_version": "empire.hermes.control_job.v1",
            "job_id": recovery_id,
            "kind": "code_task",
            "authority": request.authority,
            "base_branch": "feature/revenue-intelligence-v2",
            "prompt": (
                request.objective
                + "\n\nRECOVERY CONTEXT: retry the failed canonical job "
                + request.request_id
                + ". Preserve all original authority and evidence constraints."
            ),
            "allowed_paths": list(request.allowed_paths),
            "lease_resources": list(
                request.lease_resources
                or tuple(
                    f"path:{path}"
                    for path in request.allowed_paths
                )
            ),
            "pytest_targets": list(request.required_tests),
            "max_runtime_seconds": request.max_runtime_seconds,
            "ai_behavior_change": request.ai_behavior_change,
            "recovery_of": request.request_id,
        }
        published = publish_control_job(ROOT, payload)
        rows.append({
            "request_id": request.request_id,
            "recovery_id": recovery_id,
            "action": (
                "published"
                if published.get("published")
                else "already_queued"
            ),
            "original_status": status,
            "execution_authority": "none",
        })

    print(json.dumps({
        "schema_version": "empire.predictive-hermes-recovery.v1",
        "recovery_count": len(rows),
        "recoveries": rows,
        "production_deploy": False,
        "external_execution_performed": False,
        "execution_authority": "none",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
