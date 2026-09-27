from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.demand_api import create_demand_router
from empire_os.demand_comparison import compare_demand_plan_outcomes
from empire_os.demand_freshness import review_demand_outcome_evidence
from empire_os.demand_outcome import DemandOutcomeEvidence


NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


def review(plan_id, observed_value, cost, metric="qualified_inbound"):
    return review_demand_outcome_evidence(
        DemandOutcomeEvidence(
            plan_id=plan_id,
            success_metric=metric,
            baseline_value=10.0,
            observed_value=observed_value,
            observed_cost_cents=cost,
            observed_at="2026-09-20T11:00:00+00:00",
            evidence_refs=(f"outcome:{plan_id}", f"cost:{plan_id}"),
        ),
        plan_registered_at="2026-09-19T12:00:00+00:00",
        now=NOW,
    )


def test_two_fresh_realized_plans_are_comparable_without_selection():
    result = compare_demand_plan_outcomes(
        review("plan-a", 15.0, 5000),
        review("plan-b", 18.0, 5600),
    )
    assert result.comparison_available is True
    assert result.absolute_change_delta == 3.0
    assert result.cost_per_incremental_unit_delta_cents == -300.0
    assert result.automatic_plan_selection is False
    assert result.execution_authority == "none"
    assert result.publishing_enabled is False


def test_metric_mismatch_blocks_comparison():
    result = compare_demand_plan_outcomes(
        review("plan-a", 15.0, 5000),
        review("plan-b", 18.0, 5600, metric="revenue"),
    )
    assert result.comparison_available is False
    assert "success_metric_mismatch" in result.blockers
    assert result.absolute_change_delta is None


def test_incomplete_efficiency_blocks_comparison():
    result = compare_demand_plan_outcomes(
        review("plan-a", 15.0, 5000),
        review("plan-b", 10.0, 5600),
    )
    assert result.comparison_available is False
    assert "comparable_cost_efficiency_unavailable" in result.blockers


def request_item(plan_id, observed_value, cost):
    return {
        "plan_id": plan_id,
        "success_metric": "qualified_inbound",
        "baseline_value": 10,
        "observed_value": observed_value,
        "observed_cost_cents": cost,
        "observed_at": "2026-09-20T11:00:00+00:00",
        "evidence_refs": [f"outcome:{plan_id}", f"cost:{plan_id}"],
        "plan_registered_at": "2026-09-19T12:00:00+00:00",
        "now_utc": "2026-09-20T12:00:00+00:00",
    }


def test_api_comparison_is_non_executing():
    app = FastAPI()
    app.include_router(create_demand_router())
    response = TestClient(app).post(
        "/v1/demand/outcome/comparison/preview",
        json={
            "left": request_item("plan-a", 15, 5000),
            "right": request_item("plan-b", 18, 5600),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["recommendation_only"] is True
    assert body["execution_authority"] == "none"
    assert body["publishing_enabled"] is False
    assert body["outbound_enabled"] is False
    assert body["ad_spend_enabled"] is False
    assert body["provider_activation_enabled"] is False
    assert body["automatic_plan_selection"] is False
    assert body["comparison"]["comparison_available"] is True
