"""Read-only truth custody and decision evidence inventory for Predictive Revenue.

Uses original aggregate Revenue Pulse and Economic Memory sources, not private
customer episodes, bank records or financial transaction APIs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json

from empire_os.predictive_profitability_governed_decision import (
    review_existing_global_economics_truth_runtime,
)
from scripts.review_predictive_profitability_playbooks_20261019 import (
    build_live_profitability_readiness,
)
from empire_os.predictive_customer_value_outcome_readiness import (
    review_customer_value_outcome_readiness_runtime,
)
from empire_os.predictive_customer_value_radar_bridge import (
    review_customer_value_radar_bridge_runtime,
)


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--read-only",required=True,action="store_true")
    p.add_argument("--repo-root",default="/srv/empire_os")
    args=p.parse_args()
    now=datetime.now(timezone.utc)
    truth=review_existing_global_economics_truth_runtime(args.repo_root,as_of=now)
    outcome=review_customer_value_outcome_readiness_runtime(args.repo_root,as_of=now)
    radar=review_customer_value_radar_bridge_runtime(args.repo_root,as_of=now)
    readiness=build_live_profitability_readiness(outcome,radar)
    output={
        "schema_version":"empire.predictive_revenue.economic_decision_source_handoff.v1",
        "status":"READ_ONLY_ECONOMIC_DECISION_SOURCE_REVIEW",
        "mode":"OBSERVE",
        "economic_truth":truth,
        "source_readiness":{
            "status":readiness["status"],
            "radar_customer_value_source_aligned":readiness["radar_customer_value_source_aligned"],
            "read_only_aggregate_outcome_source_ready":readiness["read_only_aggregate_outcome_source_ready"],
            "verified_community_radar_opportunities_in_review":readiness["verified_community_radar_opportunities_in_review"],
            "source_outcomes_observed_in_quant_snapshot":readiness["source_outcomes_observed_in_quant_snapshot"],
            "probability_ready_product_count":readiness["probability_ready_product_count"],
            "profitability_forecast_calibrated":False,
            "scenario_profit_for_production_available":False,
        },
        "founder_profitability_decision_authorized":False,
        "company_revenue_is_specific_pilot_outcome":False,
        "source_outcomes_can_train_quant":False,
        "registered_original_forecast_looked_up":False,
        "next_owner":"existing_finance_predictive_decision_control_and_scientific_quant_owners",
        "next_action":"BIND_SOURCE_VERIFIED_PILOT_FORECAST_PURCHASE_COST_AND_ECONOMIC_MEMORY_REF",
        "outbound_sent":False,"database_writes":False,
        "execution_authority":"none",
    }
    print(json.dumps(output,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
