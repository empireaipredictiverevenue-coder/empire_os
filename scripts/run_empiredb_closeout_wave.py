#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from empire_os.data_cloud_closeout_dispatcher import dispatch_closeout_wave


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--queue-pi-only",
        action="store_true",
        help="queue Pi requests instead of executing Pi sandboxes immediately",
    )
    parser.add_argument("--max-parallel", type=int, default=4)
    args = parser.parse_args()

    payload = dispatch_closeout_wave(
        execute_pi=not args.queue_pi_only,
        max_parallel=args.max_parallel,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 2 if payload["dispatch_failure_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
