from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.demand_api import create_demand_router
from empire_os.demand_outcome import (
    DemandOutcomeEvidence,
    review_demand_outcome,
)


def evidence(**overrides):
    values = {
        "plan_id": "plan-1",
        "success_metric": "qualified_inbound_conversations",
        "baseline_value": 10.0,
        "observed_value": 15.0,
        "observed_cost_cents": 5000,
        "observed_at": "2026-09-20T14:00:00+00:00",
        "evidence_refs": ("crm:outcomes:1",),
    }
    values.update(overrides)
    return DemandOutcomeEvidence(**values)


def test_observed_outcome_computes_change_only():
    result = review_demand_outcome(evidence())
    assert result.outcome_available is True
    assert result.absolute_change == 5.0
    assert result.relative_change == 0.5
    assert result.execution_authority == "none"
    assert result.publishing_enabled is False
    assert result.outbound_enabled is False
    assert result.ad_spend_enabled is False


def test_missing_observed_value_stays_unknown():
    result = review_demand_outcome(
        evidence(observed_value=None)
    )
    assert result.outcome_available is False
    assert result.absolute_change is None
    assert result.relative_change is None
    assert result.blockers == (
        "success_metric_outcome_evidence_incomplete",
    )


def test_zero_baseline_does_not_invent_relative_change():
    result = review_demand_outcome(
        evidence(baseline_value=0.0, observed_value=4.0)
    )
    assert result.outcome_available is True
    assert result.absolute_change == 4.0
    assert result.relative_change is None


def test_api_preview_is_non_executing():
    app = FastAPI()
    app.include_router(create_demand_router())
    response = TestClient(app).post(
        "/v1/demand/outcome/preview",
        json={
            "plan_id": "plan-1",
            "success_metric": "qualified_inbound_conversations",
            "baseline_value": 10,
            "observed_value": 15,
            "observed_cost_cents": 5000,
            "observed_at": "2026-09-20T14:00:00+00:00",
            "evidence_refs": ["crm:outcomes:1"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_authority"] == "none"
    assert body["publishing_enabled"] is False
    assert body["outbound_enabled"] is False
    assert body["ad_spend_enabled"] is False
    assert body["provider_activation_enabled"] is False
    assert body["outcome_review"]["outcome_available"] is True
