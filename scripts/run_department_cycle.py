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
    args = parser.parse_args()
    payload = run_department_cycle(
        args.repo_root,
        max_items=args.max_items,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    worker_ok = (payload.get("worker") or {}).get("ok")
    return 0 if worker_ok is not False else 1


if __name__ == "__main__":
    raise SystemExit(main())
