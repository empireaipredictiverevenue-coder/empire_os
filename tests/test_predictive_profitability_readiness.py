"""Founder's read-only economics/operator readiness preserves unknowns."""
import json

from scripts.review_predictive_profitability_playbooks_20261019 import (
    PILLARS, PLAYBOOKS, build_live_profitability_readiness,
)


def test_no_real_payment_price_or_profit_in_fake_ready_snapshot():
    report=build_live_profitability_readiness({
        "status":"CUSTOMER_VALUE_OUTCOME_SOURCE_READINESS_REVIEWED",
        "predictive_source_outcome_count":0,
        "probability_ready_product_count":0,
        "buyer_identity":"not-permitted@example.com",
    },{
        "status":"CUSTOMER_VALUE_TO_RADAR_RESEARCH_BRIDGED",
        "community_radar_candidate_count":2,
        "market_research_candidate_count":11,
        "secret_url":"https://private.example",
    })
    assert report["verified_community_radar_opportunities_in_review"]==2
    assert report["source_outcomes_observed_in_quant_snapshot"]==0
    assert report["profitability_forecast_calibrated"] is False
    assert report["realized_gross_profit_authenticated_by_this_review"] is False
    assert report["buyer_purchase_prices_authenticated"] is False
    assert report["product_level_costs_authenticated"] is False
    assert report["scenario_profit_for_production_available"] is False
    assert len(report["architecture_pillars"])>=15
    assert len(report["next_existing_owner_playbooks"])>=8
    assert all(row["approved_or_executed"] is False
               for row in report["next_existing_owner_playbooks"])
    assert "not-permitted@example.com" not in json.dumps(report)
    assert "https://private.example" not in json.dumps(report)
    assert report["spend_authorized"] is False
    assert report["database_writes"] is False


def test_source_hold_is_unknown_not_zero_or_sales_ready():
    r=build_live_profitability_readiness(
        {"status":"CANONICAL_AGGREGATE_SOURCE_HOLD",
         "predictive_source_outcome_count":1000},
        {"status":"SOURCE_EVIDENCE_HOLD",
         "community_radar_candidate_count":1000},
    )
    assert r["source_outcomes_observed_in_quant_snapshot"] is None
    assert r["verified_community_radar_opportunities_in_review"] is None
    assert r["profitability_forecast_calibrated"] is False
    assert r["execution_authority"]=="none"
