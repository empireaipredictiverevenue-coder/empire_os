#!/usr/bin/env python3
"""Run one bounded canonical Lead Scoring v2 qualification cycle."""
from __future__ import annotations

import argparse
import json

from empire_os.qualification_worker_v2 import run_cycle


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 25:
        parser.error("--limit must be between 1 and 25")
    result = run_cycle(args.limit)
    print(json.dumps(result, indent=2, default=str))
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
