#!/usr/bin/env python3
"""One bounded ASTRA-owned deep research step; no separate timer or agent loop."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path

# Limit public provider attempts inside ASTRA's existing service timeout.
os.environ.setdefault("EMPIRE_SEARCH_PUBLIC_TIMEOUT_SECONDS", "3")
os.environ.setdefault("EMPIRE_SEARCH_PUBLIC_ATTEMPTS", "1")
from empire_os.system_improvement_research import OUTPUT, research_once
from empire_os.opportunity_evidence_resolver import refresh as refresh_evidence
from empire_os.system_improvement_review import refresh_review_packets


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--max-queries", type=int, default=1)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    folder = root / OUTPUT
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / ".single_writer.lock").open("a") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({"status": "ALREADY_RUNNING",
                              "execution_authority": "none"}))
            return 0
        # Shadow resolver runs alongside the existing evidence pipeline.
        # No score is returned or written to the Factory normalizer.
        resolver = refresh_evidence(root)
        report = research_once(
            root, max_queries=args.max_queries, force=args.force,
        )
        review = refresh_review_packets(root)
        print(json.dumps({
            "research": report,
            "evidence_shadow": {
                "opportunities": resolver["opportunities"],
                "unresolved_requirements": resolver["unresolved_requirements"],
                "reason_counts": resolver["reason_counts"],
                "normalized_scores_written": 0,
            },
            "review_queue": {
                "task_count": review.get("task_count", 0),
                "new_or_changed": review.get("new_or_changed_review_packets", 0),
                "auto_dispatch_eligible": False,
                "department_work_queue_mutated": False,
            },
            "execution_authority": "none",
        }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
