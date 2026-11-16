#!/usr/bin/env python3
"""Existing Hermes timer's bounded Empire Coder isolated-candidate handoff."""
from __future__ import annotations

import argparse
import json

from empire_os.coder.isolated_implement_drain import drain_isolated_implement_jobs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--max-jobs", type=int, default=1)
    args = parser.parse_args()
    if not (1 <= args.max_jobs <= 2):
        parser.error("max-jobs must be 1 or 2")
    result = drain_isolated_implement_jobs(args.repo_root, max_jobs=args.max_jobs)
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0 if result["failed_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
