from datetime import date, timedelta

from empire_os.predictive_cloud_v3 import ObservedMetricPoint
from empire_os.trend_regime import classify_trend_regime


def points(values):
    start = date(2026, 9, 1)
    return [
        ObservedMetricPoint(
            observed_date=start + timedelta(days=i),
            value=value,
            source="canonical_actuals",
        )
        for i, value in enumerate(values)
    ]


def test_insufficient_history_stays_unknown():
    result = classify_trend_regime(
        metric="buyer_conversations",
        points=points([0, 0, 1]),
    )
    assert result.available is False
    assert result.regime == "insufficient_history"


def test_clean_uptrend_is_expansion():
    result = classify_trend_regime(
        metric="buyer_conversations",
        points=points([10, 11, 12, 13, 14, 15, 16]),
        volatile_threshold=.5,
    )
    assert result.available is True
    assert result.trend == "up"
    assert result.regime == "expansion"


def test_high_variance_series_is_volatile():
    result = classify_trend_regime(
        metric="opportunity_count",
        points=points([1, 20, 1, 20, 1, 20, 1]),
        volatile_threshold=.25,
    )
    assert result.available is True
    assert result.regime == "volatile"
