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
    worker_ok = (payload.get("worker") or {}).get("ok")

    # Process health is separate from department-work truth.
    # FAILED/BLOCKED work remains persisted in the durable queue and
    # executive evaluation, but a successfully completed heartbeat
    # must not poison systemd health or stop future queue processing.
    payload["service_health"] = "completed"
    payload["work_ok"] = worker_ok is not False

    print(json.dumps(payload, indent=2, sort_keys=True))

    # Any real process defect still raises before this point and
    # therefore exits non-zero naturally.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
