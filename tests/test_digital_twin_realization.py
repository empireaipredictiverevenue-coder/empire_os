from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.digital_twin import MarketScenarioResult
from empire_os.digital_twin_api import create_digital_twin_router
from empire_os.digital_twin_realization import (
    ObservedMarketOutcome,
    review_scenario_realization,
)


def scenario():
    return MarketScenarioResult(
        scenario_id="scenario-1",
        projected_demand_units=120,
        projected_capacity_units=100,
        projected_served_units=100,
        projected_price_per_unit_cents=10000,
        projected_revenue_cents=1000000,
    )


def outcome(**overrides):
    values = {
        "observed_served_units": 90,
        "observed_revenue_cents": 950000,
        "revenue_recognized": True,
        "observed_at": "2026-09-20T12:00:00+00:00",
        "evidence_refs": (
            "market:served:1",
            "revenue:recognized:1",
        ),
    }
    values.update(overrides)
    return ObservedMarketOutcome(**values)


def test_realization_compares_observed_outcome():
    result = review_scenario_realization(
        scenario=scenario(),
        observed=outcome(),
    )
    assert result.served_unit_error == -10
    assert result.revenue_error_cents == -50000
    assert result.revenue_error_ratio == -0.05
    assert result.revenue_comparison_available is True
    assert result.simulation_only is True
    assert result.creates_actual_revenue is False


def test_unrecognized_revenue_stays_unavailable():
    result = review_scenario_realization(
        scenario=scenario(),
        observed=outcome(
            observed_revenue_cents=950000,
            revenue_recognized=False,
        ),
    )
    assert result.observed_revenue_cents is None
    assert result.revenue_error_cents is None
    assert result.revenue_error_ratio is None
    assert result.revenue_comparison_available is False
    assert result.blockers == (
        "recognized_revenue_evidence_missing",
    )


def test_realization_preview_api_never_mutates():
    app = FastAPI()
    app.include_router(create_digital_twin_router())
    client = TestClient(app)
    response = client.post(
        "/v1/digital-twin/realization/preview",
        json={
            "baseline": {
                "niche": "roofing",
                "metro": "London",
                "observed_demand_units": 100,
                "observed_capacity_units": 80,
                "observed_price_per_unit_cents": 10000,
                "observed_at": "2026-09-19T20:00:00+00:00",
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
            "observed_at": "2026-09-20T12:00:00+00:00",
            "evidence_refs": [
                "market:served:1",
                "revenue:recognized:1",
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["simulation_only"] is True
    assert body["creates_actual_revenue"] is False
    assert body["execution_authority"] == "none"
    assert body["capital_execution"] is False
    assert body["campaign_execution"] is False
    assert body["pricing_execution"] is False
    assert body["review"]["revenue_comparison_available"] is True
