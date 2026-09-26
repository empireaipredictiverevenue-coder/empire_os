from datetime import date, timedelta

from empire_os.search_traffic_forecast import (
    DailySearchObservation,
    aggregate_search_console_daily,
    forecast_search_traffic,
)
from empire_os.timesfm_shadow import TimesFmShadowForecast


class FakeTimesFm:
    def status(self):
        return {"available": True}

    def forecast(self, *, metric, values, horizon_steps):
        value = 100.0 if metric == "search_impressions" else 10.0
        return TimesFmShadowForecast(
            available=True,
            metric=metric,
            horizon_steps=horizon_steps,
            context_samples=len(values),
            model_id="fake-timesfm",
            point_forecast=tuple(value for _ in range(horizon_steps)),
        )


def observations(days=14):
    start = date(2026, 9, 1)
    return [
        DailySearchObservation(
            observed_date=start + timedelta(days=i),
            impressions=100 + i * 10,
            clicks=10 + i,
        )
        for i in range(days)
    ]


def test_timesfm_shadow_forecasts_clicks_impressions_and_ctr():
    bundle = forecast_search_traffic(
        observations(),
        horizon_days=7,
        timesfm_provider=FakeTimesFm(),
    )
    assert bundle.available is True
    assert bundle.timesfm_horizon_impressions == 700.0
    assert bundle.timesfm_horizon_clicks == 70.0
    assert bundle.timesfm_horizon_ctr == 0.1
    assert bundle.creates_actuals is False
    assert bundle.creates_revenue is False


def test_aggregate_search_console_daily_rows():
    rows = [
        {"keys": ["2026-09-01"], "impressions": 100, "clicks": 10},
        {"keys": ["2026-09-01"], "impressions": 50, "clicks": 5},
        {"keys": ["2026-09-02"], "impressions": 80, "clicks": 4},
    ]
    output = aggregate_search_console_daily(rows)
    assert len(output) == 2
    assert output[0].impressions == 150
    assert output[0].clicks == 15


def test_disabled_timesfm_preserves_baseline_forecast():
    bundle = forecast_search_traffic(observations(), horizon_days=7)
    assert bundle.baseline_impressions["available"] is True
    assert bundle.baseline_clicks["available"] is True
    assert bundle.timesfm_horizon_impressions is None
    assert bundle.mode == "SHADOW_COMPARE"
