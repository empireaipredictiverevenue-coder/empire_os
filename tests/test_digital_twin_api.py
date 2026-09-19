from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.digital_twin_api import create_digital_twin_router


def client():
    app = FastAPI()
    app.include_router(create_digital_twin_router())
    return TestClient(app)


def payload():
    return {
        "baseline": {
            "niche": "roofing",
            "metro": "London",
            "observed_demand_units": 20,
            "observed_capacity_units": 10,
            "observed_price_per_unit_cents": 10000,
            "observed_at": "2026-09-19T18:30:00+00:00",
            "evidence_ref": "exchange-observation-1",
        },
        "scenario": {
            "scenario_id": "scenario-1",
            "demand_multiplier": 1.0,
            "capacity_multiplier": 2.0,
            "price_multiplier": 1.0,
        },
    }


def test_health_is_simulation_only():
    response = client().get("/v1/digital-twin/health")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "SIMULATION"
    assert body["simulation_only"] is True
    assert body["actual_revenue"] is False
    assert body["execution_authority"] == "none"


def test_preview_returns_simulated_delta_only():
    response = client().post("/v1/digital-twin/preview", json=payload())
    assert response.status_code == 200
    body = response.json()
    assert body["simulation_only"] is True
    assert body["actual_revenue"] is False
    assert body["execution_authority"] == "none"
    comparison = body["comparison"]
    assert comparison["baseline_revenue_cents"] == 100000
    assert comparison["scenario"]["projected_revenue_cents"] == 200000
    assert comparison["scenario"]["actual_revenue"] is False


def test_negative_multiplier_is_rejected_by_schema():
    body = payload()
    body["scenario"]["demand_multiplier"] = -1
    response = client().post("/v1/digital-twin/preview", json=body)
    assert response.status_code == 422


def test_missing_baseline_provenance_is_rejected():
    body = payload()
    body["baseline"]["evidence_ref"] = ""
    response = client().post("/v1/digital-twin/preview", json=body)
    assert response.status_code == 422
    assert "baseline provenance required" in response.json()["detail"]
