"""Read-only founder economic decision planning status for Predictive Revenue.

Never fabricate buyer price, conversion, CAC, margin, cash flow, event receipts,
model probabilities or a live playbook from missing source inputs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json

from empire_os.predictive_customer_value_outcome_readiness import (
    review_customer_value_outcome_readiness_runtime,
)
from empire_os.predictive_customer_value_radar_bridge import (
    review_customer_value_radar_bridge_runtime,
)

PILLARS = {
    "world_and_market_signals":"existing Source/Community/Market Radar owners",
    "entity_resolution_and_temporal_graph":"existing Source Intelligence/Knowledge Graph owner",
    "company_market_consumer_product_digital_twins":"existing Digital Twin and Market Knowledge Graph",
    "jobs_to_be_done_and_purchasing_intent":"existing Community Intent + customer value research",
    "willingness_to_pay_and_competitor_pricing":"existing Market Research/Strategy/Commerce owners",
    "original_deal_and_revenue_prediction":"existing original conversion registry / Quant",
    "profitability_margin_cac_ltv_break_even":"feature: predictive_profitability_playbooks",
    "cash_exposure_and_payment_timing":"feature: predictive_profitability_playbooks",
    "downside_base_upside_sensitivity":"existing strategic scenarios + feature economic book",
    "risk_tail_and_value_of_information":"existing quant_brain + feature economic book",
    "portfolio_capital_allocation":"existing predictive_cloud_scenario_optimization",
    "governed_action_playbooks":"existing Strategy/Departments + feature trigger descriptions",
    "customer_time_and_money_outcomes":"feature: customer value measurement preflight",
    "paid_orders_renewals_refunds_bookings":"feature: commerce evidence preflight",
    "recognized_gross_profit_and_economic_memory":"existing Economic Memory/Outcome owner",
    "forecast_error_backtests_and_calibration":"existing Quant calibration and original registry",
}

PLAYBOOKS = (
    ("source_intelligence", "VERIFY_RESEARCH_PROVENANCE_BEFORE_MARKET_RANKING"),
    ("buyer_qualification", "VERIFY_FIRST_PARTY_BUYER_PRICE_TERRITORY_CAPACITY_AND_RIGHTS"),
    ("pricing_strategy", "OBTAIN_PURCHASE_PRICE_UNIT_AND_COMPETITIVE_WILLINGNESS_TO_PAY"),
    ("unit_economics", "EVIDENCE_ACQUISITION_FULFILMENT_SUPPORT_FEES_REFUNDS_AND_RETENTION"),
    ("scenario_science", "FREEZE_DOWNSIDE_BASE_UPSIDE_ASSUMPTIONS_BEFORE_OUTCOMES"),
    ("capital_governance", "SET_MAX_CASH_EXPOSURE_CAPACITY_AND_STOP_LOSS_BEFORE_SPEND"),
    ("scientific_quant", "REGISTER_ORIGINAL_FORECAST_AND_BASELINE_BEFORE_OUTCOMES"),
    ("customer_value", "OBTAIN_CONSENTED_TIME_COST_AND_QUALITY_BASELINES"),
    ("revenue_truth", "LINK_PAYMENT_FULFILMENT_REVERSALS_COST_AND_CUSTOMER_FEEDBACK"),
    ("learning", "CALIBRATE_ONLY_WITH_REAL_REGISTERED_FORECAST_OUTCOME_PAIRS"),
)


def build_live_profitability_readiness(
    outcome: dict, radar: dict,
) -> dict:
    if not isinstance(outcome,dict) or not isinstance(radar,dict):
        raise ValueError("source owner reports required")
    status=outcome.get("status")
    radar_status=radar.get("status")
    trusted=status=="CUSTOMER_VALUE_OUTCOME_SOURCE_READINESS_REVIEWED"
    aligned=radar_status=="CUSTOMER_VALUE_TO_RADAR_RESEARCH_BRIDGED"
    return {
        "schema_version":"empire.predictive_revenue.economics_playbook_readiness.v1",
        "mode":"OBSERVE",
        "status":"ORIGINAL_REVENUE_ECONOMICS_INPUTS_INCOMPLETE",
        "read_only_aggregate_outcome_source_ready":trusted,
        "radar_customer_value_source_aligned":aligned,
        "verified_community_radar_opportunities_in_review":(
            radar.get("community_radar_candidate_count") if aligned else None
        ),
        "separate_market_research_records":(
            radar.get("market_research_candidate_count") if aligned else None
        ),
        "source_outcomes_observed_in_quant_snapshot":(
            outcome.get("predictive_source_outcome_count") if trusted else None
        ),
        "probability_ready_product_count":(
            outcome.get("probability_ready_product_count") if trusted else None
        ),
        "customer_savings_authenticated":False,
        "buyer_purchase_prices_authenticated":False,
        "product_level_costs_authenticated":False,
        "profitability_forecast_calibrated":False,
        "realized_gross_profit_authenticated_by_this_review":False,
        "scenario_profit_for_production_available":False,
        "scenario_inputs_missing": [
            "original_pilot_and_prospective_prediction_registry",
            "accepted_buyer_or_customer_price_currency_and_purchased_unit",
            "qualified_attempt_volume_and_calibrated_conversion_distribution",
            "delivery_processing_support_acquisition_and_fixed_costs",
            "refund_cancellation_churn_and_repeat_paid_cycle_distribution",
            "cash_collection_terms_and_capital_constraints",
            "source_authentication_and_verified_profit_outcome_feedback",
        ],
        "architecture_pillars": dict(PILLARS),
        "next_existing_owner_playbooks": [
            {"owner":owner,"action":action,"approved_or_executed":False}
            for owner,action in PLAYBOOKS
        ],
        "new_model_training":False, "new_research_crawl":False,
        "capital_allocation_execution":False, "spend_authorized":False,
        "outbound_sent":False, "database_writes":False,
        "execution_authority":"none",
    }


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--read-only",action="store_true",required=True)
    p.add_argument("--repo-root",default="/srv/empire_os")
    args=p.parse_args()
    now=datetime.now(timezone.utc)
    outcome=review_customer_value_outcome_readiness_runtime(args.repo_root,as_of=now)
    radar=review_customer_value_radar_bridge_runtime(args.repo_root,as_of=now)
    result=build_live_profitability_readiness(outcome,radar)
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
