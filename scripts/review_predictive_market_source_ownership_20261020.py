"""Predictive source custody review: real restricted reply lineage + GPS code drift.

No database connection, sends, worker activation, model weight mutation or
promotion to a verified buyer or authenticated profit forecast.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json

from empire_os.predictive_market_restricted_provenance import (
    review_restricted_reply_lineage_runtime,
    review_market_gps_merge_compatibility,
)


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--read-only",action="store_true",required=True)
    p.add_argument("--repo-root",default="/srv/empire_os")
    p.add_argument("--feature-root",default="/home/ubuntu/empire_agents/predictive_decision_control_20261018")
    args=p.parse_args()
    now=datetime.now(timezone.utc)
    lineage=review_restricted_reply_lineage_runtime(args.repo_root,as_of=now)
    drift=review_market_gps_merge_compatibility(args.feature_root,args.repo_root)
    result={
        "schema_version":"empire.predictive_revenue.territory_source_ownership_handoff.v1",
        "status":"TERRITORY_SOURCE_OWNERSHIP_REVIEWED",
        "mode":"OBSERVE",
        "restricted_lineage":lineage,
        "producer_compatibility":drift,
        "source_owner_merge_authority":False,
        "original_forecast_or_buyer_activation_performed":False,
        "source_intelligence_read_only":True,
        "outbound_sent":False,"database_writes":False,
        "execution_authority":"none",
    }
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
