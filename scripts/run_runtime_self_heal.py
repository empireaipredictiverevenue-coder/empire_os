#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from empire_os.runtime_self_heal import run_runtime_self_heal


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observe-only", action="store_true")
    args = parser.parse_args()

    payload = run_runtime_self_heal(observe_only=args.observe_only)
    print(json.dumps({
        "ok": payload["status"] == "HEALTHY",
        "status": payload["status"],
        "check_count": payload["check_count"],
        "unresolved_count": payload["unresolved_count"],
        "repair_count": payload["repair_count"],
        "observe_only": payload["observe_only"],
        "execution_authority": payload["execution_authority"],
        "actual_revenue": payload["actual_revenue"],
    }, indent=2, sort_keys=True))
    # Component degradation is represented in the health snapshot. The
    # controller itself remains runnable so the timer can keep repairing.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
