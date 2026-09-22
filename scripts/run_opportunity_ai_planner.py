#!/usr/bin/env python3
"""Queue bounded Empire Coder plans for fresh Opportunity Radar candidates."""
from __future__ import annotations

import argparse
import json

from empire_os.opportunity_ai_planner import plan_radar_opportunities


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()

    result = plan_radar_opportunities(
        args.repo_root,
        limit=args.limit,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
