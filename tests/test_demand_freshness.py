from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.demand_api import create_demand_router
from empire_os.demand_freshness import review_demand_outcome_evidence
from empire_os.demand_outcome import DemandOutcomeEvidence


NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


def evidence(**overrides):
    values = {
        "plan_id": "plan-1",
        "success_metric": "qualified_inbound_conversations",
        "baseline_value": 10.0,
        "observed_value": 15.0,
        "observed_cost_cents": 5000,
        "observed_at": "2026-09-20T11:00:00+00:00",
        "evidence_refs": ("crm:outcomes:1", "cost:observed:1"),
    }
    values.update(overrides)
    return DemandOutcomeEvidence(**values)


def test_fresh_positive_increment_exposes_observed_cost_efficiency():
    result = review_demand_outcome_evidence(
        evidence(),
        plan_registered_at="2026-09-19T12:00:00+00:00",
        now=NOW,
    )
    assert result.review_ready is True
    assert result.freshness == "fresh"
    assert result.outcome_after_plan is True
    assert result.absolute_change == 5.0
    assert result.cost_efficiency_available is True
    assert result.cost_per_incremental_unit_cents == 1000.0
    assert result.execution_authority == "none"
    assert result.publishing_enabled is False
    assert result.outbound_enabled is False


def test_missing_cost_preserves_unknown_efficiency():
    result = review_demand_outcome_evidence(
        evidence(observed_cost_cents=None),
        plan_registered_at="2026-09-19T12:00:00+00:00",
        now=NOW,
    )
    assert result.review_ready is False
    assert result.cost_efficiency_available is False
    assert result.cost_per_incremental_unit_cents is None
    assert "observed_cost_evidence_missing" in result.blockers


def test_flat_or_negative_outcome_does_not_invent_efficiency():
    flat = review_demand_outcome_evidence(
        evidence(observed_value=10.0),
        plan_registered_at="2026-09-19T12:00:00+00:00",
        now=NOW,
    )
    negative = review_demand_outcome_evidence(
        evidence(observed_value=8.0),
        plan_registered_at="2026-09-19T12:00:00+00:00",
        now=NOW,
    )
    assert flat.cost_per_incremental_unit_cents is None
    assert negative.cost_per_incremental_unit_cents is None
    assert "positive_incremental_outcome_not_observed" in flat.blockers
    assert "positive_incremental_outcome_not_observed" in negative.blockers


def test_outcome_before_plan_is_blocked():
    result = review_demand_outcome_evidence(
        evidence(observed_at="2026-09-19T11:00:00+00:00"),
        plan_registered_at="2026-09-19T12:00:00+00:00",
        now=NOW,
    )
    assert result.review_ready is False
    assert result.outcome_after_plan is False
    assert "outcome_not_after_registered_plan" in result.blockers


def test_stale_and_future_outcome_evidence_are_explicit():
    stale = review_demand_outcome_evidence(
        evidence(observed_at="2026-09-18T12:00:00+00:00"),
        plan_registered_at="2026-09-17T12:00:00+00:00",
        now=NOW,
        max_age_seconds=21600,
    )
    future = review_demand_outcome_evidence(
        evidence(observed_at="2026-09-20T12:05:00+00:00"),
        plan_registered_at="2026-09-19T12:00:00+00:00",
        now=NOW,
        max_age_seconds=21600,
    )
    assert "outcome_evidence_stale" in stale.blockers
    assert "outcome_evidence_future" in future.blockers


def test_api_preview_is_observe_only():
    app = FastAPI()
    app.include_router(create_demand_router())
    response = TestClient(app).post(
        "/v1/demand/outcome/evidence/preview",
        json={
            "plan_id": "plan-1",
            "success_metric": "qualified_inbound_conversations",
            "baseline_value": 10,
            "observed_value": 15,
            "observed_cost_cents": 5000,
            "observed_at": "2026-09-20T11:00:00+00:00",
            "evidence_refs": ["crm:outcomes:1", "cost:observed:1"],
            "plan_registered_at": "2026-09-19T12:00:00+00:00",
            "now_utc": "2026-09-20T12:00:00+00:00",
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
    assert body["review"]["review_ready"] is True
    assert body["review"]["cost_per_incremental_unit_cents"] == 1000.0


def test_api_rejects_naive_now_timestamp():
    app = FastAPI()
    app.include_router(create_demand_router())
    response = TestClient(app).post(
        "/v1/demand/outcome/evidence/preview",
        json={
            "plan_id": "plan-1",
            "success_metric": "qualified_inbound_conversations",
            "baseline_value": 10,
            "observed_value": 15,
            "observed_cost_cents": 5000,
            "observed_at": "2026-09-20T11:00:00+00:00",
            "evidence_refs": ["crm:outcomes:1"],
            "plan_registered_at": "2026-09-19T12:00:00+00:00",
            "now_utc": "2026-09-20T12:00:00",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "now_utc must include timezone"
