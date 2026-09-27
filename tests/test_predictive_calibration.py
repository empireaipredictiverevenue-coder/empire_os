from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.predictive_api import create_predictive_router
from empire_os.predictive_calibration import (
    ForecastActualEvidence,
    review_forecast_calibration,
)
from empire_os.predictive_materializer import materialize_daily_actuals


def rows(values=(100, 120, 140, 160, 180, 200, 220)):
    return [
        {
            "snapshot_date": f"2026-09-{index:02d}",
            "actual_value": value,
            "source": "canonical_daily_actuals",
        }
        for index, value in enumerate(values, start=1)
    ]


def materialization(*, horizon=3, values=(100, 120, 140, 160, 180, 200, 220)):
    return materialize_daily_actuals(
        metric="recognized_revenue_cents",
        rows=rows(values),
        value_field="actual_value",
        date_field="snapshot_date",
        horizon_days=horizon,
    )


def test_exact_target_actual_produces_calibration_without_mutation():
    review = review_forecast_calibration(
        materialization=materialization(),
        actual=ForecastActualEvidence(
            metric="recognized_revenue_cents",
            observed_date=date(2026, 9, 10),
            actual_value=300,
            source="canonical_recognized_revenue_actual",
        ),
    )
    assert review.calibration_ready is True
    assert review.target_date == "2026-09-10"
    assert review.predicted_value == 280.0
    assert review.actual_value == 300
    assert review.signed_error == 20.0
    assert review.absolute_error == 20.0
    assert review.relative_error == 0.0714
    assert review.bias == "under_predicted"
    assert review.execution_authority == "none"
    assert review.forecast_mutation is False
    assert review.model_weight_mutation is False
    assert review.accounting_mutation is False
    assert review.creates_actual_revenue is False


def test_early_or_late_actual_does_not_calibrate_target_forecast():
    review = review_forecast_calibration(
        materialization=materialization(),
        actual=ForecastActualEvidence(
            metric="recognized_revenue_cents",
            observed_date=date(2026, 9, 9),
            actual_value=280,
            source="canonical_actual",
        ),
    )
    assert review.calibration_ready is False
    assert "actual_date_does_not_match_forecast_target" in review.blockers
    assert review.signed_error is None
    assert review.bias == "unknown"


def test_insufficient_history_cannot_be_calibrated():
    review = review_forecast_calibration(
        materialization=materialization(values=(100, 110, 120)),
        actual=ForecastActualEvidence(
            metric="recognized_revenue_cents",
            observed_date=date(2026, 9, 6),
            actual_value=150,
            source="canonical_actual",
        ),
    )
    assert review.calibration_ready is False
    assert "forecast_not_available_for_calibration" in review.blockers
    assert review.predicted_value is None


def test_overprediction_and_on_target_are_descriptive_only():
    over = review_forecast_calibration(
        materialization=materialization(),
        actual=ForecastActualEvidence(
            metric="recognized_revenue_cents",
            observed_date=date(2026, 9, 10),
            actual_value=260,
            source="canonical_actual",
        ),
    )
    exact = review_forecast_calibration(
        materialization=materialization(),
        actual=ForecastActualEvidence(
            metric="recognized_revenue_cents",
            observed_date=date(2026, 9, 10),
            actual_value=280,
            source="canonical_actual",
        ),
    )
    assert over.bias == "over_predicted"
    assert over.signed_error == -20.0
    assert exact.bias == "on_target"
    assert exact.signed_error == 0.0
    assert over.model_weight_mutation is False
    assert exact.forecast_mutation is False


def test_api_calibration_preview_is_observe_only():
    app = FastAPI()
    app.include_router(create_predictive_router())
    response = TestClient(app).post(
        "/v1/predictive/forecast/calibration/preview",
        json={
            "preview": {
                "metric": "recognized_revenue_cents",
                "horizon_days": 3,
                "points": [
                    {
                        "observed_date": f"2026-09-{index:02d}",
                        "value": value,
                        "source": "canonical_daily_actuals",
                    }
                    for index, value in enumerate(
                        [100, 120, 140, 160, 180, 200, 220],
                        start=1,
                    )
                ],
            },
            "actual_observed_date": "2026-09-10",
            "actual_value": 300,
            "actual_source": "canonical_recognized_revenue_actual",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_authority"] == "none"
    assert body["write_authority"] == "none"
    assert body["synthetic_data_allowed"] is False
    assert body["forecast_mutation"] is False
    assert body["model_weight_mutation"] is False
    assert body["commercial_execution"] is False
    assert body["accounting_mutation"] is False
    assert body["creates_actual_revenue"] is False
    assert body["calibration"]["calibration_ready"] is True
