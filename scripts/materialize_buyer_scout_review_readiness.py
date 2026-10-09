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
from empire_os.buyer_evidence_quality_scorecard import refresh_evidence_quality_scorecard
from empire_os.revenue_flow_meter import refresh_flow_meter


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

    # Existing scheduled worker now emits a read-only, cohort-safe quality
    # receipt. Failure of optional reporting must never bypass policy gates,
    # change database state or interrupt buyer review processing.
    quality_status = "unavailable"
    quality_summary = {}
    try:
        quality = refresh_evidence_quality_scorecard(args.repo_root)
        quality_status = (
            "current" if quality["stage_receipts_time_aligned"]
            and quality["scout_receipt_fresh"] else "stale_or_mismatched_snapshots"
        )
        quality_summary = {
            "scout_candidate_count": quality["scout_candidate_count"],
            "verified_direct_purchase_receipt_count": quality[
                "candidate_with_valid_direct_purchase_receipt"
            ],
            "strict_named_person_email_binding_count": quality[
                "candidate_with_strict_named_person_email_binding"
            ],
        }
    except Exception as exc:
        print("EVIDENCE_QUALITY_SCORECARD_UNAVAILABLE:" + type(exc).__name__ + ":" + str(exc)[:180])

    # Use this existing scheduled materializer: no additional timer or agent.
    # Aggregate-only report is advisory. Failure never grants approval and
    # never interrupts the governed review workflow above.
    flow_status = "unavailable"
    flow_summary = {}
    try:
        flow = refresh_flow_meter(args.repo_root)
        checks = flow["health_checks"]
        upstream_current = (
            checks["scout_fresh"]
            and checks["scout_to_reconciliation_verified"]
            and checks["evidence_quality_aligned"]
            and checks["review_fresh"]
        )
        flow_status = (
            "fully_current" if upstream_current
            and checks["commercial_truth_fresh"]
            and checks["revenue_truth_fresh"]
            else "upstream_current_downstream_stale" if upstream_current
            else "partial_or_stale"
        )
        flow_summary = {
            "scout_domain_join_count": flow["handoffs"][
                "scout_to_reconciliation"
            ]["joined_count"],
            "review_inventory_scanned": flow["stages"][
                "holding_review_scanned"
            ]["current_count"],
            "astra_canonical_company_matches": flow["stages"][
                "astra_canonical_bindings"
            ]["current_count"],
            "commercial_funnel_current": flow["health_checks"][
                "commercial_truth_fresh"
            ],
        }
    except Exception as exc:
        print("REVENUE_FLOW_METER_UNAVAILABLE:" + type(exc).__name__ + ":" + str(exc)[:180])

    print(json.dumps({
        "flow_meter_status": flow_status,
        "flow_meter_summary": flow_summary,
        "evidence_quality_status": quality_status,
        "evidence_quality_summary": quality_summary,
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
