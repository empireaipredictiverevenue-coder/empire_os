#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from empire_os.swarm_v6 import run_swarm_cycle


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument(
        "--enqueue-only",
        action="store_true",
        help="enqueue specialist VERIFY work but do not execute it",
    )
    args = parser.parse_args()

    result = run_swarm_cycle(
        max_workers=args.max_workers,
        execute_verify=not args.enqueue_only,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    failed = any(
        row.get("status") == "FAILED"
        for row in result.get("executions", [])
    )
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
