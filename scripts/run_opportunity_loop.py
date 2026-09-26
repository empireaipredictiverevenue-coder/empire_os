#!/usr/bin/env python3
"""Run the canonical autonomous Predictive Cloud Opportunity Loop."""
from __future__ import annotations

import argparse
import json

from empire_os.opportunity_loop import run_opportunity_loop


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument(
        "--min-interval-seconds",
        type=int,
        default=900,
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    payload = run_opportunity_loop(
        args.repo_root,
        min_interval_seconds=args.min_interval_seconds,
        force=args.force,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
