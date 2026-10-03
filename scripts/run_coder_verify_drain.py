#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.coder import EmpireCoder
from empire_os.coder.jobs import JobKind, LocalJobQueue
from empire_os.coder.worker import CoderTaskWorker
from empire_os.completion_reconciliation import (
    refresh_completion_reconciliation,
)
from empire_os.completion_verify_recovery import (
    recover_failed_completion_verifications,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default="/srv/empire_os")
    parser.add_argument("--runtime-root", default="/srv/empire_os/runtime/coder")
    parser.add_argument("--max-jobs", type=int, default=4)
    args = parser.parse_args()

    root = Path(args.workspace).resolve()
    coder = EmpireCoder(root, runtime_root=args.runtime_root)
    queue = LocalJobQueue(root, runtime_root=args.runtime_root)
    worker = CoderTaskWorker(coder, queue)
    pre_reconciliation = refresh_completion_reconciliation(root)
    recovery = recover_failed_completion_verifications(
        root,
        reconciliation=pre_reconciliation,
        max_groups=max(1, min(int(args.max_jobs), 8)),
    )

    rows = []
    for _ in range(max(1, min(int(args.max_jobs), 12))):
        job = worker.run_once(kind=JobKind.VERIFY)
        if job is None:
            break
        rows.append({
            "job_id": job.id,
            "status": job.status.value,
            "attempts": job.attempts,
        })

    reconciliation = refresh_completion_reconciliation(root)
    print(json.dumps({
        "schema_version": "empire.coder.verify-drain.v1",
        "status": "AVAILABLE",
        "processed_count": len(rows),
        "jobs": rows,
        "completion_verify_recovery": {
            "queued_group_count": recovery.get("queued_group_count"),
            "queued_item_count": recovery.get("queued_item_count"),
            "retry_only_after_relevant_content_change": recovery.get(
                "retry_only_after_relevant_content_change"
            ),
        },
        "completion_reconciliation": {
            "status": reconciliation.get("status"),
            "state_counts": reconciliation.get("state_counts") or {},
            "remediation_candidate_count": reconciliation.get(
                "remediation_candidate_count"
            ),
            "live_proof_candidate_count": reconciliation.get(
                "live_proof_candidate_count"
            ),
        },
        "model_inference": False,
        "production_mutation": False,
        "execution_authority": "none",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
