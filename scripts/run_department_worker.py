#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from empire_os.department_worker import run_department_worker

def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--max-items", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args=parser.parse_args()
    payload=run_department_worker(
        args.repo_root,
        max_items=args.max_items,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("ok") else 1

if __name__ == "__main__":
    raise SystemExit(main())
