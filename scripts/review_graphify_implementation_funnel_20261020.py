"""Founder-approved, non-mutating Coder PLAN-to-IMPLEMENT blocker review.

Checks the actual existing job queue, original founder directive records,
approved plan-promotion contract validation, and live shared Git cleanliness.
Never queues IMPLEMENT or forges contracts or approval.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.graphify_implementation_funnel import review_implementation_funnel


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("/srv/empire_os"))
    parser.add_argument("--lookback-hours", type=int, default=24)
    parser.add_argument("--read-only", action="store_true", required=True)
    args = parser.parse_args()
    report = review_implementation_funnel(
        args.repo_root, as_of=datetime.now(timezone.utc),
        lookback_hours=args.lookback_hours,
    )
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
