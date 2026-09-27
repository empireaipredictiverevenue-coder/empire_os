#!/usr/bin/env python3
"""Run bounded source-targeted canonical qualification."""
from __future__ import annotations

import argparse
import json

from empire_os.source_qualification_bridge import run_source_qualification


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--niche", default=None)
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    if args.limit < 1 or args.limit > 25:
        parser.error("--limit must be between 1 and 25")

    result = run_source_qualification(
        source=args.source,
        niche=args.niche,
        limit=args.limit,
    )
    print(json.dumps(result, indent=2, default=str))
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
