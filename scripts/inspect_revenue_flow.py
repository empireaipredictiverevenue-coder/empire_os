#!/usr/bin/env python3
"""Observe current EmpireOS revenue flow; --refresh writes aggregate receipts."""
from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import json

from empire_os.revenue_flow_meter import (
    _load_receipts, build_flow_meter, refresh_flow_meter,
)


def main() -> int:
    parser = ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("/srv/empire_os"))
    parser.add_argument("--refresh", action="store_true",
                        help="Write local read-only-derived flow receipts and history")
    args = parser.parse_args()
    root = args.repo_root.resolve()
    if args.refresh:
        report = refresh_flow_meter(root)
    else:
        report = build_flow_meter(_load_receipts(root))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
