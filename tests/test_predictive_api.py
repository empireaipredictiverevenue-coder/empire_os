from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.predictive_api import create_predictive_router


def client():
    app = FastAPI()
    app.include_router(create_predictive_router())
    return TestClient(app)


def points(values):
    return [
        {
            "observed_date": f"2026-09-{index + 1:02d}",
            "value": value,
            "source": "canonical_daily_actuals",
        }
        for index, value in enumerate(values)
    ]


def test_health_disallows_synthetic_and_writes():
    response = client().get("/v1/predictive/health")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_authority"] == "none"
    assert body["write_authority"] == "none"
    assert body["synthetic_data_allowed"] is False


def test_forecast_preview_uses_observed_actuals():
    response = client().post(
        "/v1/predictive/forecast/preview",
        json={
            "metric": "actual_revenue_cents",
            "horizon_days": 3,
            "points": points([100, 120, 140, 160, 180, 200, 220]),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["write_authority"] == "none"
    forecast = body["materialization"]["forecast"]
    assert forecast["available"] is True
    assert forecast["direction"] == "up"
    assert forecast["predicted_value"] == 280.0


def test_short_history_stays_insufficient():
    response = client().post(
        "/v1/predictive/forecast/preview",
        json={
            "metric": "actual_revenue_cents",
            "horizon_days": 7,
            "points": points([100, 120, 140]),
        },
    )
    assert response.status_code == 200
    forecast = response.json()["materialization"]["forecast"]
    assert forecast["available"] is False
    assert forecast["direction"] == "insufficient_history"


def test_missing_source_provenance_fails_closed():
    data = points([100])
    data[0]["source"] = ""
    response = client().post(
        "/v1/predictive/forecast/preview",
        json={
            "metric": "actual_revenue_cents",
            "horizon_days": 7,
            "points": data,
        },
    )
    assert response.status_code == 422
    assert "source provenance" in response.json()["detail"]


def test_negative_actual_is_rejected_by_schema():
    response = client().post(
        "/v1/predictive/forecast/preview",
        json={
            "metric": "actual_revenue_cents",
            "horizon_days": 7,
            "points": [{
                "observed_date": "2026-09-01",
                "value": -1,
                "source": "canonical_daily_actuals",
            }],
        },
    )
    assert response.status_code == 422
