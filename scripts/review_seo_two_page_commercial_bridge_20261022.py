"""Read-only count-only SEO-to-commercial evidence review from existing sources.

Needs an explicitly authorised local root operator for existing read-only
EmpireDB/CRM probes. No SQL is introduced and no payment or outbound action.
No inferred traffic source when the original intake lacks trusted entry proof.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
import os

from empire_os.search_intelligence.seo_to_commercial_evidence import (
    CommercialEvidenceHeld, build_commercial_bridge,
)
from scripts.report_weekly_two_page_gsc_20261022 import run as gsc_report
from scripts.reconcile_founder_sales_handoff_aggregate_readonly import run as sales_probe


def review(as_of:date) -> dict:
    if os.geteuid()!=0:
        return {
            "status":"HELD_EXISTING_COUNT_ONLY_DB_OPERATOR_REQUIRED",
            "database_writes":False,
            "execution_authority":"NONE",
        }
    gsc=gsc_report(as_of=as_of,write_private=False)
    crm=sales_probe(privileged=True)
    try:
        result=build_commercial_bridge(gsc,crm)
    except CommercialEvidenceHeld:
        return {
            "status":"HELD_CANONICAL_EVIDENCE_NOT_JOINABLE",
            "canonical_source_status":crm.get("status","SOURCE_UNAVAILABLE"),
            "new_data_access_roles_granted":False,
            "database_writes":False,
            "execution_authority":"NONE",
        }
    return result


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--as-of",type=date.fromisoformat,
                        default=datetime.now(timezone.utc).date())
    parser.add_argument("--review-only",action="store_true")
    args=parser.parse_args()
    if not args.review_only:
        print(json.dumps({"status":"REVIEW_ONLY_FLAG_REQUIRED",
                          "database_writes":False,"execution_authority":"NONE"}))
        return
    try:
        print(json.dumps(review(args.as_of),sort_keys=True))
    except (OSError,TypeError,ValueError) as exc:
        print(json.dumps({"status":"HELD_SOURCE_REPORT_UNAVAILABLE",
                          "database_writes":False,"execution_authority":"NONE"}))
        raise SystemExit(2) from None


if __name__=="__main__":
    main()
