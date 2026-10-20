"""Read-only Newsjack / existing JEV owner -> Predictive research intake.

The existing JEV/Newsjack owner supplies any JSON review packets. This
operator never runs a news crawler, PR agent, plugin installer, or campaign.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.predictive_real_world_newsjack import (
    review_newsjack_source_readiness_runtime,
    review_existing_jev_newsjack_handoff,
)
from empire_os.predictive_market_evidence_binding import (
    review_revenue_gps_territory_evidence_runtime,
)


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",required=True,action="store_true")
    parser.add_argument("--repo-root",default="/srv/empire_os")
    parser.add_argument("--jev-owner-review",default=None,
                        help="Explicit JEV Newsjack read-only owner review JSON")
    args=parser.parse_args()
    now=datetime.now(timezone.utc)
    source=review_newsjack_source_readiness_runtime(args.repo_root,as_of=now)
    market=review_revenue_gps_territory_evidence_runtime(args.repo_root,as_of=now)
    jev=None
    if args.jev_owner_review:
        file=Path(args.jev_owner_review)
        if (file.is_symlink() or not file.is_file()
                or not 0<file.stat().st_size<=1_000_000):
            raise SystemExit("JEV_OWNER_REVIEW_FILE_UNAVAILABLE_OR_UNTRUSTED")
        with file.open("r",encoding="utf-8") as stream:
            packet=json.load(stream)
        jev=review_existing_jev_newsjack_handoff(packet,as_of=now)
    output={
        "schema_version":"empire.predictive_revenue.newsjack_operator.v1",
        "status":"NEWSJACK_SOURCE_AND_TERRITORY_READINESS_REVIEWED",
        "mode":"OBSERVE",
        "news_source_readiness":source,
        "existing_jev_newsjack_owner_handoff":jev,
        "original_jev_newsjack_review_supplied":args.jev_owner_review is not None,
        "upstream_newsjack_repo_auto_installed":False,
        "territory_source_status":market.get("status"),
        "territory_research_market_count":market.get("market_count"),
        "territory_source_revision_sha256":market.get("source_revision_fingerprint"),
        "news_as_purchased_demand_allowed":False,
        "incremental_profit_calibration_performed":False,
        "news_crawling_enabled":False,
        "websites_changed":False,"outbound_sent":False,
        "database_writes":False,"execution_authority":"none",
    }
    print(json.dumps(output,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
