#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.parse

from empire_os.buyer_scout_review_readiness import (
    materialize_review_readiness,
    quarantine_stale_official_readiness,
    write_review_readiness,
)
from empire_os.sb import request_json


def _audit_stale_ready(*, limit: int, observe_only: bool) -> dict:
    query = urllib.parse.urlencode({
        "select": (
            "id,business_name,domain,query_evidence,site_evidence,"
            "review_state,reconciliation_state,"
            "canonical_prospect_id,canonical_buyer_id"
        ),
        "review_state": "eq.review_ready",
        "reconciliation_state": "eq.REVIEW_READY",
        "canonical_prospect_id": "is.null",
        "canonical_buyer_id": "is.null",
        "order": "reviewed_at.asc",
        "limit": str(max(1, min(int(limit), 200))),
    })
    rows = request_json("GET", "/rest/v1/buyer_scout_candidates?" + query) or []
    if not isinstance(rows, list):
        raise ValueError("stale_ready_inventory_must_be_list")
    return quarantine_stale_official_readiness(
        [row for row in rows if isinstance(row, dict)],
        patch_call=None if observe_only else lambda method, path, body: request_json(
            method, path, payload=body, prefer="return=representation",
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--observe-only", action="store_true", help="Evaluate evidence without database updates")
    args = parser.parse_args()

    # Preserve the existing buyer-scout owner; only repair false-ready
    # unpromoted holding records, never create a prospect or send mail.
    stale_audit = _audit_stale_ready(
        limit=args.limit, observe_only=args.observe_only,
    )

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
        patch_call=None if args.observe_only else lambda method, path, body: request_json(
            method,
            path,
            payload=body,
            prefer="return=representation",
        ),
    )
    payload["historical_official_identity_quarantine"] = stale_audit
    payload["database_write_performed"] = bool(
        payload["database_write_performed"]
        or stale_audit["database_write_performed"]
    )
    write_review_readiness(args.repo_root, payload)

    print(json.dumps({
        "ok": True,
        "candidate_count": payload["candidate_count"],
        "review_ready_count": payload["review_ready_count"],
        "blocked_count": payload["blocked_count"],
        "historical_identity_mismatch_count": len(stale_audit["mismatch_ids"]),
        "historical_identity_quarantined_count": stale_audit["quarantined_count"],
        "database_write_performed": (
            payload["database_write_performed"]
            or stale_audit["database_write_performed"]
        ),
        "canonical_promotion_performed": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
