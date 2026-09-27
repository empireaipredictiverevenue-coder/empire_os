from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.demand_api import create_demand_router
from empire_os.demand_commercial_impact import (
    DemandCommercialImpactEvidence,
    review_demand_commercial_impact,
)
from empire_os.demand_freshness import DemandOutcomeEvidenceReview


def outcome(**overrides):
    values = {
        "plan_id": "plan-1",
        "success_metric": "qualified_demand",
        "outcome_age_seconds": 3600.0,
        "freshness": "fresh",
        "outcome_after_plan": True,
        "outcome_available": True,
        "absolute_change": 10.0,
        "observed_cost_cents": 5000,
        "cost_per_incremental_unit_cents": 500.0,
        "cost_efficiency_available": True,
        "review_ready": True,
        "blockers": (),
    }
    values.update(overrides)
    return DemandOutcomeEvidenceReview(**values)


def evidence(**overrides):
    values = {
        "plan_id": "plan-1",
        "commercial_attribution_ref": "attribution:plan-1:revenue-1",
        "recognized_revenue_ref": "revenue:recognized:1",
        "recognized_revenue_cents": 15000,
        "realized_gp_ref": "gross-profit:1",
        "realized_gp_cents": 9000,
    }
    values.update(overrides)
    return DemandCommercialImpactEvidence(**values)


def test_actual_revenue_and_gp_require_explicit_attribution_evidence():
    review = review_demand_commercial_impact(
        outcome=outcome(),
        evidence=evidence(),
    )
    assert review.commercial_impact_ready is True
    assert review.recognized_revenue_cents == 15000
    assert review.realized_gp_cents == 9000
    assert review.revenue_on_cost == 3.0
    assert review.gross_profit_on_cost == 1.8
    assert review.execution_authority == "none"
    assert review.revenue_mutation is False
    assert review.accounting_mutation is False


def test_metric_lift_alone_is_never_revenue():
    review = review_demand_commercial_impact(
        outcome=outcome(),
        evidence=evidence(
            commercial_attribution_ref=None,
            recognized_revenue_ref=None,
            recognized_revenue_cents=None,
            realized_gp_ref=None,
            realized_gp_cents=None,
        ),
    )
    assert review.commercial_impact_ready is False
    assert review.recognized_revenue_cents is None
    assert "commercial_attribution_evidence_missing" in review.blockers
    assert "recognized_revenue_value_unknown" in review.blockers


def test_stale_or_blocked_demand_outcome_blocks_commercial_impact():
    review = review_demand_commercial_impact(
        outcome=outcome(
            review_ready=False,
            blockers=("outcome_evidence_stale",),
        ),
        evidence=evidence(),
    )
    assert review.commercial_impact_ready is False
    assert "demand_outcome_not_review_ready" in review.blockers
    assert "outcome_evidence_stale" in review.blockers


def test_zero_cost_keeps_return_ratios_unknown_without_inventing_values():
    review = review_demand_commercial_impact(
        outcome=outcome(
            observed_cost_cents=0,
            cost_per_incremental_unit_cents=None,
        ),
        evidence=evidence(),
    )
    assert review.commercial_impact_ready is True
    assert review.revenue_on_cost is None
    assert review.gross_profit_on_cost is None


def test_api_commercial_impact_is_observe_only():
    app = FastAPI()
    app.include_router(create_demand_router())
    response = TestClient(app).post(
        "/v1/demand/outcome/commercial-impact/preview",
        json={
            "plan_id": "plan-1",
            "success_metric": "qualified_demand",
            "baseline_value": 10,
            "observed_value": 20,
            "observed_cost_cents": 5000,
            "observed_at": "2026-09-20T15:00:00+00:00",
            "evidence_refs": ["outcome:1", "cost:1"],
            "plan_registered_at": "2026-09-20T12:00:00+00:00",
            "now_utc": "2026-09-20T16:00:00+00:00",
            "commercial_attribution_ref": "attribution:plan-1:revenue-1",
            "recognized_revenue_ref": "revenue:recognized:1",
            "recognized_revenue_cents": 15000,
            "realized_gp_ref": "gross-profit:1",
            "realized_gp_cents": 9000,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_authority"] == "none"
    assert body["publishing_enabled"] is False
    assert body["outbound_enabled"] is False
    assert body["ad_spend_enabled"] is False
    assert body["revenue_mutation"] is False
    assert body["accounting_mutation"] is False
    assert body["impact"]["commercial_impact_ready"] is True
