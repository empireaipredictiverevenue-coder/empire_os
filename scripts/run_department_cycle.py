#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from empire_os.department_cycle import run_department_cycle


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--max-items", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    payload = run_department_cycle(
        args.repo_root,
        max_items=args.max_items,
        timeout_seconds=args.timeout_seconds,
    )
    worker_ok = (payload.get("worker") or {}).get("ok")

    # Process health is separate from department-work truth.
    # FAILED/BLOCKED work remains persisted in the durable queue and
    # executive evaluation, but a successfully completed heartbeat
    # must not poison systemd health or stop future queue processing.
    payload["service_health"] = "completed"
    payload["work_ok"] = worker_ok is not False

    if args.verbose:
        output = payload
    else:
        live = dict(payload.get("live_queue_truth") or {})
        completion = dict(payload.get("completion_progress") or {})
        optimization = dict(
            payload.get("business_optimization_automation") or {}
        )
        policy = dict(payload.get("business_optimization_policy") or {})
        output = {
            "schema_version": payload.get("schema_version"),
            "service_health": payload.get("service_health"),
            "work_ok": payload.get("work_ok"),
            "worker": payload.get("worker") or {},
            "evaluation_state": dict(
                payload.get("evaluation") or {}
            ).get("evaluation_state"),
            "master_checklist": completion.get("master_checklist") or {},
            "active_execution_backlog": live.get(
                "active_execution_backlog"
            ),
            "coder_active_pending_count": live.get(
                "coder_active_pending_count"
            ),
            "coder_active_running_count": live.get(
                "coder_active_running_count"
            ),
            "coder_active_delegated_count": live.get(
                "coder_active_delegated_count"
            ),
            "department_active_count": live.get(
                "department_active_count"
            ),
            "optimization_processed_count": optimization.get(
                "processed_request_count"
            ),
            "optimization_queue_remaining": optimization.get(
                "queued_request_count_remaining"
            ),
            "optimization_active_policy_count": policy.get(
                "active_policy_count"
            ),
            "optimization_partial_evidence_count": policy.get(
                "partial_evidence_count"
            ),
            "external_execution_performed": payload.get(
                "external_execution_performed"
            ),
            "execution_authority": payload.get("execution_authority"),
        }
    print(json.dumps(output, indent=2, sort_keys=True))

    # Any real process defect still raises before this point and
    # therefore exits non-zero naturally.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
