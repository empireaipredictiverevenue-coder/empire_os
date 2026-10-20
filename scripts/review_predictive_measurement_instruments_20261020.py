"""One read-only Predictive + Storm measurement readiness operator.

No private source event bodies, outbound, database queries/writes, model
fitting, revenue activation, paid services or exporter installation.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.predictive_market_evidence_binding import (
    review_revenue_gps_territory_evidence_runtime,
)
from empire_os.predictive_market_restricted_provenance import (
    review_restricted_reply_lineage_runtime,
    review_market_gps_merge_compatibility,
)
from empire_os.predictive_customer_value_outcome_readiness import (
    review_customer_value_outcome_readiness_runtime,
)
from empire_os.predictive_profitability_governed_decision import (
    review_existing_global_economics_truth_runtime,
)
from empire_os.predictive_storm_measurement import review_storm_measurement_runtime
from empire_os.predictive_bls_cost_index import review_bls_cost_index_owner
from empire_os.predictive_measurement_instruments import (
    build_predictive_measurement_instruments,
)


def main() -> int:
    parser=argparse.ArgumentParser(description="Predictive Revenue measurement and Storm product evidence scorecard")
    parser.add_argument("--read-only",action="store_true",required=True)
    parser.add_argument("--repo-root",default="/srv/empire_os")
    parser.add_argument("--feature-root",default="/home/ubuntu/empire_agents/predictive_decision_control_20261018")
    parser.add_argument("--bls-owner-review",default=None,
                        help="Existing BLS economic-source owner's reviewed read-only JSON")
    args=parser.parse_args()
    now=datetime.now(timezone.utc)
    territory=review_revenue_gps_territory_evidence_runtime(args.repo_root,as_of=now)
    lineage=review_restricted_reply_lineage_runtime(args.repo_root,as_of=now)
    outcomes=review_customer_value_outcome_readiness_runtime(args.repo_root,as_of=now)
    global_economics=review_existing_global_economics_truth_runtime(args.repo_root,as_of=now)
    producer=review_market_gps_merge_compatibility(args.feature_root,args.repo_root)
    storm=review_storm_measurement_runtime(args.repo_root,as_of=now)
    bls_packet=None
    if args.bls_owner_review:
        file=Path(args.bls_owner_review)
        if file.is_symlink() or not file.is_file() or not 0<file.stat().st_size<=1_000_000:
            raise SystemExit("BLS_OWNER_REVIEW_FILE_UNAVAILABLE_OR_UNTRUSTED")
        with file.open("r",encoding="utf-8") as stream:
            bls_packet=json.load(stream)
    bls=review_bls_cost_index_owner(bls_packet,as_of=now)
    report=build_predictive_measurement_instruments(
        territory,lineage,outcomes,global_economics,producer,storm,as_of=now,bls=bls,
    )
    print(json.dumps(report,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
