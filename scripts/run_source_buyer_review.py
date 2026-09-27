#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from empire_os.source_buyer_review_bridge import run_source_buyer_review


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--niche", default=None)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--proposal-limit", type=int, default=10)
    parser.add_argument("--min-company-score", type=float, default=70.0)
    parser.add_argument(
        "--prospect-id",
        action="append",
        default=[],
        help="Optional exact hot-source prospect id; may be repeated.",
    )
    args = parser.parse_args()

    result = run_source_buyer_review(
        source=args.source,
        niche=args.niche,
        limit=args.limit,
        proposal_limit=args.proposal_limit,
        min_company_score=args.min_company_score,
        prospect_ids=args.prospect_id or None,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    errors = result["materializer"].get("errors") or []
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
