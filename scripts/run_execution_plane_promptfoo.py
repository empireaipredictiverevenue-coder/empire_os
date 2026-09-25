#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from empire_os.execution_plane_promptfoo import run_pending_promptfoo


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-items", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()

    result = run_pending_promptfoo(
        "/srv/empire_os",
        max_items=args.max_items,
        timeout_seconds=args.timeout,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 2 if result["failed_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
