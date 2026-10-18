#!/usr/bin/env python3
"""Private, read-only buyer evidence triage using the existing EmpireDB reader.

No file output, DB mutation, worker queue, send, quote or financial approval.
Buyer organisation names are redacted unless explicitly requested.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json

from empire_os.buyer_specific_buybox_review import review_buyer_buybox_candidates


def review_existing_buyers(
    *,
    buyer_rows,
    niche: str = "",
    metro: str = "",
    include_names: bool = False,
    limit: int = 8,
    as_of: datetime | None = None,
) -> dict:
    """Injectable source means offline tests never connect to production."""
    if type(niche) is not str or type(metro) is not str:
        raise ValueError("market filters must be text")
    if len(niche) > 100 or len(metro) > 100:
        raise ValueError("market filter too long")
    source = list(buyer_rows)
    if len(source) > 10000:
        raise ValueError("review cap exceeded; do not silently truncate")
    chosen = [
        row for row in source
        if isinstance(row, dict)
        and (not niche or niche.casefold() in str(row.get("niche") or "").casefold())
        and (not metro or metro.casefold() in str(row.get("metro") or "").casefold())
    ]
    result = review_buyer_buybox_candidates(
        chosen, max_candidates=limit,
        as_of=as_of or datetime.now(timezone.utc),
    )
    result["filters"] = {
        "niche": niche or None,
        "metro": metro or None,
    }
    result["company_names_exposed"] = bool(include_names)
    if not include_names:
        for record in result["candidates"]:
            record["buyer_name"] = None
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EmpireOS: bounded read-only buyer-specific evidence review",
    )
    parser.add_argument("--niche", default="", help="e.g. solar")
    parser.add_argument("--metro", default="", help="e.g. Bolton")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--include-buyer-names", action="store_true")
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 15:
        parser.error("--limit must be between 1 and 15")

    # This is the existing canonical EmpireDB buyer reader. Do not add a
    # second datasource, alter its SQL, or persist a parallel customer cache.
    from scripts.build_buyer_capacity_readiness import fetch_all_buyers
    rows = fetch_all_buyers(max_rows=10001)
    if len(rows) > 10000:
        raise RuntimeError("buyer inventory cap exceeded; no partial preview")
    result = review_existing_buyers(
        buyer_rows=rows, niche=args.niche, metro=args.metro,
        include_names=args.include_buyer_names, limit=args.limit,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
