from datetime import date, timedelta

import pytest

from empire_os.predictive_cloud_v3 import (
    MIN_FORECAST_SAMPLES,
    ObservedMetricPoint,
    forecast_observed_metric,
)


def points(values):
    start = date(2026, 9, 1)
    return [
        ObservedMetricPoint(
            observed_date=start + timedelta(days=index),
            value=value,
            source="canonical_daily_revenue",
        )
        for index, value in enumerate(values)
    ]


def test_short_history_returns_insufficient_instead_of_guessing():
    result = forecast_observed_metric(
        metric="daily_revenue_cents",
        points=points([100, 120, 140]),
        horizon_days=7,
    )
    assert result.available is False
    assert result.direction == "insufficient_history"
    assert result.predicted_value is None
    assert result.reason == f"minimum_{MIN_FORECAST_SAMPLES}_observations_required"


def test_observed_uptrend_produces_explainable_forecast():
    result = forecast_observed_metric(
        metric="daily_revenue_cents",
        points=points([100, 120, 140, 160, 180, 200, 220]),
        horizon_days=3,
    )
    assert result.available is True
    assert result.direction == "up"
    assert result.daily_slope == 20.0
    assert result.predicted_value == 280.0
    assert result.r_squared == 1.0
    assert 0 < result.evidence_confidence <= 1


def test_flat_history_stays_flat():
    result = forecast_observed_metric(
        metric="daily_revenue_cents",
        points=points([100] * 7),
        horizon_days=30,
    )
    assert result.direction == "flat"
    assert result.predicted_value == 100.0
    assert result.r_squared == 1.0


def test_negative_observation_fails_closed():
    with pytest.raises(ValueError, match="nonnegative"):
        forecast_observed_metric(
            metric="daily_revenue_cents",
            points=points([100, 90, 80, 70, 60, 50, -1]),
            horizon_days=7,
        )


def test_forecast_horizon_is_bounded():
    with pytest.raises(ValueError, match="out of bounds"):
        forecast_observed_metric(
            metric="daily_revenue_cents",
            points=points([100] * 7),
            horizon_days=366,
        )
