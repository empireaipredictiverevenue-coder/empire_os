from datetime import datetime, timezone

from empire_os.future_trend_intelligence import analyze_future_trend


def _observations():
    return [
        {
            "observed_at": "2026-09-01T00:00:00+00:00",
            "value": 10,
            "source": "market_sweep",
            "evidence_ref": "market:1",
        },
        {
            "observed_at": "2026-09-08T00:00:00+00:00",
            "value": 14,
            "source": "community_intent",
            "evidence_ref": "intent:1",
        },
        {
            "observed_at": "2026-09-15T00:00:00+00:00",
            "value": 20,
            "source": "revenue_pulse",
            "evidence_ref": "pulse:1",
        },
        {
            "observed_at": "2026-09-22T00:00:00+00:00",
            "value": 28,
            "source": "market_sweep",
            "evidence_ref": "market:2",
        },
    ]


def test_future_trend_requires_real_time_series():
    result = analyze_future_trend(_observations()[:2])
    assert result["status"] == "UNAVAILABLE"
    assert result["reason"] == "insufficient_observed_time_series"
    assert result["actual_revenue"] is False


def test_future_trend_detects_direction_velocity_and_acceleration():
    result = analyze_future_trend(
        _observations(),
        leading_indicator_strength=0.9,
        market_saturation=0.2,
        competitive_intensity=0.3,
        now=datetime(2026, 9, 23, tzinfo=timezone.utc),
    )
    assert result["status"] == "AVAILABLE"
    assert result["direction"] == "up"
    assert result["velocity_per_day"] > 0
    assert result["acceleration_per_day"] > 0
    assert result["persistence"] == 1.0
    assert result["future_opportunity_status"] == "AVAILABLE"
    assert 0 < result["trend_opportunity_alignment"] <= 1
    assert result["causal_claim"] is False


def test_future_opportunity_preserves_missing_structural_evidence():
    result = analyze_future_trend(
        _observations(),
        now=datetime(2026, 9, 23, tzinfo=timezone.utc),
    )
    assert result["status"] == "AVAILABLE"
    assert result["future_opportunity_status"] == "UNAVAILABLE"
    assert "market_saturation" in result[
        "future_opportunity_missing_fields"
    ]
    assert result["trend_opportunity_alignment"] is None
    assert result["unknown_is_zero"] is False


def test_stale_trend_loses_confidence():
    result = analyze_future_trend(
        _observations(),
        leading_indicator_strength=0.9,
        market_saturation=0.2,
        competitive_intensity=0.3,
        now=datetime(2027, 9, 23, tzinfo=timezone.utc),
        freshness_window_days=30,
    )
    assert result["freshness"] == 0
    assert result["trend_confidence"] == 0
    assert result["trend_opportunity_alignment"] == 0
