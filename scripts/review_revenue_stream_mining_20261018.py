#!/usr/bin/env python3
"""Read existing source streams and optionally route zero-cost internal reviews.

No network, scraping, provider credentials, production DB writes or new queue.
--review-only is the default. --enqueue-internal requires explicit selection.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.revenue_stream_mining import (
    build_revenue_stream_mining,
    enqueue_existing_department_mining,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="EmpireOS existing stream mining bridge")
    parser.add_argument("--review-only", action="store_true")
    parser.add_argument("--enqueue-internal", action="store_true")
    parser.add_argument("--max-jobs", type=int, default=4)
    args = parser.parse_args()
    if args.review_only and args.enqueue_internal:
        parser.error("choose review or internal queue dispatch")
    root = Path("/srv/empire_os")
    report = build_revenue_stream_mining(root)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.enqueue_internal:
        delivered = enqueue_existing_department_mining(
            root, report, max_jobs=args.max_jobs,
        )
        print(json.dumps(delivered, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
