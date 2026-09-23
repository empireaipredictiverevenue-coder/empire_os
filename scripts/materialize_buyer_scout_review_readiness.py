#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.parse

from empire_os.buyer_scout_review_readiness import (
    materialize_review_readiness,
    write_review_readiness,
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
            "direct_buyer_score,explicit_direct_buyer_evidence,"
            "target_buyer_pools,target_product_codes,"
            "target_corridor_keys,query_evidence,site_evidence,"
            "reconciliation_state,review_state"
        ),
        "reconciliation_state": "eq.NEW_EXTERNAL_BUYER_CANDIDATE",
        "review_state": "in.(discovered,reconciled)",
        "order": "direct_buyer_score.desc,last_seen_at.desc",
        "limit": str(max(1, min(int(args.limit), 1000))),
    })
    rows = request_json(
        "GET",
        "/rest/v1/buyer_scout_candidates?" + query,
    )

    payload = materialize_review_readiness(
        [row for row in (rows or []) if isinstance(row, dict)],
        patch_call=lambda method, path, body: request_json(
            method,
            path,
            payload=body,
            headers={"Prefer": "return=representation"},
        ),
    )
    write_review_readiness(args.repo_root, payload)

    print(json.dumps({
        "ok": True,
        "candidate_count": payload["candidate_count"],
        "review_ready_count": payload["review_ready_count"],
        "blocked_count": payload["blocked_count"],
        "canonical_promotion_performed": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
