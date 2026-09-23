#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.parse
from pathlib import Path

from empire_os.buyer_scout_raw_prospect_promotion import (
    run_raw_prospect_promotion,
    write_raw_prospect_promotion,
)
from empire_os.qualification_worker_v2 import request_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--actor")
    args = parser.parse_args()

    limit = max(1, min(int(args.limit), 1000))
    query = urllib.parse.urlencode({
        "select": (
            "id,domain,business_name,website,review_state,"
            "reconciliation_state,canonical_buyer_id,"
            "canonical_prospect_id"
        ),
        "review_state": "eq.review_ready",
        "reconciliation_state": "eq.REVIEW_READY",
        "order": "reviewed_at.asc",
        "limit": str(limit),
    })
    rows = request_json(
        "GET",
        "/rest/v1/buyer_scout_candidates?" + query,
    ) or []

    payload = run_raw_prospect_promotion(
        [row for row in rows if isinstance(row, dict)],
        rpc_call=lambda method, path, body: request_json(
            method,
            path,
            payload=body,
        ),
        execute=args.execute,
        actor=args.actor,
    )
    write_raw_prospect_promotion(
        Path(args.repo_root).resolve(),
        payload,
    )

    print(json.dumps({
        "ok": True,
        "mode": payload["mode"],
        "execute_requested": payload["execute_requested"],
        "eligible_review_ready_count": payload[
            "eligible_review_ready_count"
        ],
        "promoted_count": payload["promoted_count"],
        "database_write_performed": payload[
            "database_write_performed"
        ],
        "canonical_promotion_performed": payload[
            "canonical_promotion_performed"
        ],
        "qualification_created": False,
        "buyer_created": False,
        "outbound_sent": False,
        "actual_revenue": False,
        "autonomous_execution": False,
        "standing_authority": False,
        "execution_authority": payload["execution_authority"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
