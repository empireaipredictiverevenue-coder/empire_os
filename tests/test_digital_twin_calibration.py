from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.digital_twin import MarketScenarioResult
from empire_os.digital_twin_api import create_digital_twin_router
from empire_os.digital_twin_calibration import assess_digital_twin_calibration
from empire_os.digital_twin_realization import (
    ObservedMarketOutcome,
    review_scenario_realization,
)


NOW = datetime(2026, 9, 20, 18, 0, tzinfo=timezone.utc)


def scenario():
    return MarketScenarioResult(
        scenario_id="scenario-1",
        projected_demand_units=120,
        projected_capacity_units=100,
        projected_served_units=100,
        projected_price_per_unit_cents=10000,
        projected_revenue_cents=1000000,
    )


def realization(**overrides):
    values = {
        "observed_served_units": 90,
        "observed_revenue_cents": 950000,
        "revenue_recognized": True,
        "observed_at": "2026-09-20T16:00:00+00:00",
        "evidence_refs": ("market:1", "revenue:1"),
    }
    values.update(overrides)
    observed = ObservedMarketOutcome(**values)
    return review_scenario_realization(
        scenario=scenario(),
        observed=observed,
    ), observed


def test_fresh_post_baseline_realization_is_model_review_ready():
    review, observed = realization()
    result = assess_digital_twin_calibration(
        realization=review,
        baseline_observed_at="2026-09-20T12:00:00+00:00",
        outcome_observed_at=observed.observed_at,
        now=NOW,
        max_age_seconds=21600,
    )
    assert result.ready_for_model_review is True
    assert result.blockers == ()
    assert result.outcome_age_seconds == 7200.0
    assert result.execution_authority == "none"
    assert result.model_weight_mutation is False
    assert result.capital_execution is False


def test_stale_realization_blocks_model_review():
    review, observed = realization(
        observed_at="2026-09-19T08:00:00+00:00"
    )
    result = assess_digital_twin_calibration(
        realization=review,
        baseline_observed_at="2026-09-19T06:00:00+00:00",
        outcome_observed_at=observed.observed_at,
        now=NOW,
        max_age_seconds=21600,
    )
    assert result.ready_for_model_review is False
    assert "outcome_evidence_stale" in result.blockers


def test_pre_baseline_outcome_is_blocked():
    review, observed = realization(
        observed_at="2026-09-20T11:00:00+00:00"
    )
    result = assess_digital_twin_calibration(
        realization=review,
        baseline_observed_at="2026-09-20T12:00:00+00:00",
        outcome_observed_at=observed.observed_at,
        now=NOW,
    )
    assert result.ready_for_model_review is False
    assert "outcome_not_after_baseline" in result.blockers


def test_unrecognized_revenue_blocks_calibration():
    review, observed = realization(
        observed_revenue_cents=950000,
        revenue_recognized=False,
    )
    result = assess_digital_twin_calibration(
        realization=review,
        baseline_observed_at="2026-09-20T12:00:00+00:00",
        outcome_observed_at=observed.observed_at,
        now=NOW,
    )
    assert result.ready_for_model_review is False
    assert "recognized_revenue_comparison_unavailable" in result.blockers


def test_api_calibration_preview_never_mutates():
    app = FastAPI()
    app.include_router(create_digital_twin_router())
    response = TestClient(app).post(
        "/v1/digital-twin/realization/calibration/preview",
        json={
            "baseline": {
                "niche": "roofing",
                "metro": "London",
                "observed_demand_units": 100,
                "observed_capacity_units": 80,
                "observed_price_per_unit_cents": 10000,
                "observed_at": "2026-09-20T12:00:00+00:00",
                "evidence_ref": "exchange:roofing-london",
            },
            "scenario": {
                "scenario_id": "scenario-1",
                "demand_multiplier": 1.2,
                "capacity_multiplier": 1.25,
                "price_multiplier": 1.0,
            },
            "observed_served_units": 90,
            "observed_revenue_cents": 900000,
            "revenue_recognized": True,
            "observed_at": "2026-09-20T16:00:00+00:00",
            "evidence_refs": ["market:1", "revenue:1"],
            "now_utc": "2026-09-20T18:00:00+00:00",
            "max_age_seconds": 21600,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["simulation_only"] is True
    assert body["creates_actual_revenue"] is False
    assert body["execution_authority"] == "none"
    assert body["model_weight_mutation"] is False
    assert body["capital_execution"] is False
    assert body["campaign_execution"] is False
    assert body["pricing_execution"] is False
    assert body["calibration"]["ready_for_model_review"] is True
