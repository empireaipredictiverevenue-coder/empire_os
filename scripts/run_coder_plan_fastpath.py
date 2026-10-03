#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.coder import EmpireCoder
from empire_os.coder.jobs import LocalJobQueue
from empire_os.coder.plan_fastpath import drain_fast_plans
from empire_os.coder.plan_promotion import run_plan_promotion_cycle


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--runtime-root", default="/srv/empire_os/runtime/coder")
    parser.add_argument("--max-jobs", type=int, default=80)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    runtime = Path(args.runtime_root).resolve()
    coder = EmpireCoder(root, runtime_root=runtime)
    queue = LocalJobQueue(root, runtime_root=runtime)

    fastpath = drain_fast_plans(
        coder,
        queue,
        max_jobs=args.max_jobs,
    )
    promotion = run_plan_promotion_cycle(
        root,
        max_jobs=max(100, args.max_jobs * 2),
    )

    payload = {
        "schema_version": "empire.coder.plan-fastpath-cycle.v1",
        "status": "AVAILABLE",
        "fastpath": fastpath,
        "promotion": promotion,
        "execution_authority": "none",
    }
    if args.verbose:
        output = payload
    else:
        output = {
            "schema_version": payload["schema_version"],
            "status": payload["status"],
            "fastpath_completed_count": fastpath.get("completed_count"),
            "fastpath_skipped_unrecognized_count": fastpath.get(
                "skipped_unrecognized_count"
            ),
            "promotion_scanned_count": promotion.get("scanned_count"),
            "promotion_promoted_count": promotion.get("promoted_count"),
            "promotion_held_count": promotion.get("held_count"),
            "model_inference": False,
            "production_mutation": False,
            "execution_authority": "none",
        }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
