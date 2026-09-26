#!/usr/bin/env python3
"""Idempotently resume the canonical Predictive Cloud coding-team backlog."""
from __future__ import annotations

import json
from pathlib import Path

from empire_os.builder_capabilities import builder_capability_ready
from empire_os.execution_plane_dispatcher import dispatch_execution_request
from empire_os.predictive_coding_team import (
    predictive_cloud_coding_team_requests,
)
from empire_os.predictive_coding_team_status import (
    build_predictive_coding_team_status,
)


ROOT = Path("/srv/empire_os")


def main() -> int:
    capability_path = (
        ROOT / "runtime/execution_plane/builder_capabilities.json"
    )
    aider_ready = builder_capability_ready(
        "empire_coder",
        "aider_mutation",
        path=capability_path,
    )
    structured_ready = builder_capability_ready(
        "empire_coder",
        "structured_patch_mutation",
        path=capability_path,
    )
    if not (aider_ready or structured_ready):
        print(json.dumps({
            "ok": False,
            "reason": "no_proven_empire_coder_mutation_backend",
            "aider_ready": aider_ready,
            "structured_patch_ready": structured_ready,
            "execution_authority": "none",
        }, indent=2, sort_keys=True))
        return 2

    status = build_predictive_coding_team_status(ROOT)
    by_id = {
        row["request_id"]: row
        for row in status.get("tasks", [])
    }
    dispatches = []
    skipped = []
    blockers = []

    for req in predictive_cloud_coding_team_requests():
        row = by_id.get(req.request_id) or {}
        state = row.get("state") or {}
        queue_state = str(state.get("queue_state") or "NOT_OBSERVED")
        task_status = str(state.get("status") or "").upper()

        if row.get("worker") == "hermes":
            if queue_state == "RESULT_AVAILABLE":
                if task_status in {
                    "CANDIDATE_GATE_PASSED",
                    "COMPLETED_NO_CHANGES",
                    "AWAITING_PROMPTFOO",
                }:
                    skipped.append({
                        "request_id": req.request_id,
                        "reason": "hermes_result_already_available",
                        "status": task_status,
                    })
                else:
                    blockers.append({
                        "request_id": req.request_id,
                        "reason": "existing_hermes_result_requires_review",
                        "status": task_status or "UNKNOWN",
                    })
                continue
            if queue_state == "QUEUED_OR_RUNNING":
                skipped.append({
                    "request_id": req.request_id,
                    "reason": "hermes_already_queued_or_running",
                })
                continue

        if row.get("worker") == "empire_coder":
            if queue_state in {"PENDING", "RUNNING", "COMPLETED"}:
                skipped.append({
                    "request_id": req.request_id,
                    "reason": f"empire_coder_{queue_state.lower()}",
                })
                continue

        if row.get("worker") in {"pi", "swarm_v6"}:
            if queue_state == "QUEUED":
                skipped.append({
                    "request_id": req.request_id,
                    "reason": f"{row.get('worker')}_already_queued",
                })
                continue

        dispatches.append(
            dispatch_execution_request(
                ROOT,
                req,
                execute_pi=False,
            )
        )

    payload = {
        "schema_version": "empire.predictive-coding-backlog-resume.v1",
        "ok": True,
        "aider_ready": aider_ready,
        "structured_patch_ready": structured_ready,
        "dispatched_count": len(dispatches),
        "skipped_count": len(skipped),
        "blocker_count": len(blockers),
        "dispatches": dispatches,
        "skipped": skipped,
        "blockers": blockers,
        "production_deploy": False,
        "external_execution_performed": False,
        "execution_authority": "none",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not blockers else 3


if __name__ == "__main__":
    raise SystemExit(main())
