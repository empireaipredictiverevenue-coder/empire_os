#!/usr/bin/env python3
"""Run one bounded canonical Lead Scoring v2 qualification cycle."""
from __future__ import annotations

import argparse
import json

from empire_os.qualification_worker_v2 import (
    run_cycle,
    run_identity_catchup,
)
from empire_os.omega_worker import run_omega_cycle


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument(
        "--identity-catchup-limit",
        type=int,
        default=5,
    )
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 25:
        parser.error("--limit must be between 1 and 25")
    if args.identity_catchup_limit < 0 or args.identity_catchup_limit > 25:
        parser.error("--identity-catchup-limit must be between 0 and 25")

    qualification = run_cycle(args.limit)
    catchup = (
        run_identity_catchup(args.identity_catchup_limit)
        if args.identity_catchup_limit
        else {
            "schema_version": "qualification_identity_catchup.v1",
            "ok": True,
            "attempted": 0,
            "qualified": 0,
            "failed": 0,
            "identity_resolved": 0,
            "results": [],
            "errors": [],
        }
    )
    omega = run_omega_cycle(args.limit)
    result = {
        "schema_version": "qualification_service_cycle.v2",
        "qualification": qualification,
        "identity_catchup": catchup,
        "omega_projection": omega,
        "ok": bool(
            qualification["ok"]
            and catchup["ok"]
            and omega["ok"]
        ),
    }
    print(json.dumps(result, indent=2, default=str))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
