#!/usr/bin/env python3
"""Read-only CLI for the Orchestration Integrity Guardian."""
from __future__ import annotations
import argparse
import json
from empire_os.orchestration_integrity_guardian import run_guardian

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default="/srv/empire_os")
    p.add_argument("--check-release", action="store_true")
    args = p.parse_args()
    r = run_guardian(args.repo_root)
    print(json.dumps({
        "status": r["status"], "release_gate": r["release_gate"],
        "finding_count": r["finding_count"],
        "queue_truth": {
            k:r["queue_truth"].get(k) for k in (
                "unresolved_count", "blocked_or_failed_count",
                "stage_only_done_not_implementation_count", "unowned_exceptions"
            )
        },
        "service_truth": {
            k:r["service_truth"].get(k)
            for k in ("post_hook_count","drop_in_count","sub_state")
        },
        "report": "runtime/orchestration_integrity/latest.json",
        "findings": r["findings"],
    }, indent=2,sort_keys=True))
    return 3 if args.check_release and r["release_gate"] == "REJECT" else 0

if __name__ == "__main__":
    raise SystemExit(main())
