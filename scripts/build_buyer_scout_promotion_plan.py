#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.parse

from empire_os.buyer_scout_promotion_plan import (
    build_promotion_plan,
    write_promotion_plan,
)
from empire_os.qualification_worker_v2 import request_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    query = urllib.parse.urlencode({
        "select": (
            "id,domain,business_name,website,buyer_type,"
            "target_buyer_pools,target_product_codes,"
            "target_corridor_keys,site_evidence,"
            "reconciliation_state,review_state"
        ),
        "reconciliation_state": "eq.REVIEW_READY",
        "review_state": "eq.review_ready",
        "order": "direct_buyer_score.desc,last_seen_at.desc",
        "limit": str(max(1, min(int(args.limit), 1000))),
    })
    rows = request_json(
        "GET",
        "/rest/v1/buyer_scout_candidates?" + query,
    )
    payload = build_promotion_plan(
        [row for row in (rows or []) if isinstance(row, dict)]
    )
    write_promotion_plan(args.repo_root, payload)

    print(json.dumps({
        "ok": True,
        "proposal_count": payload["proposal_count"],
        "blocked_count": payload["blocked_count"],
        "database_write_performed": False,
        "canonical_promotion_performed": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
