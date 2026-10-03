from empire_os.outbound_health_forecast import forecast_reputation_health


def test_forecast_preemptively_flags_rising_bounce_rate():
    result = forecast_reputation_health([
        {"bounce_rate": 0.010, "complaint_rate": 0, "inbox_placement_rate": 0.97},
        {"bounce_rate": 0.018, "complaint_rate": 0, "inbox_placement_rate": 0.96},
        {"bounce_rate": 0.024, "complaint_rate": 0, "inbox_placement_rate": 0.95},
    ])
    assert result["posture"] == "PREEMPTIVE_THROTTLE"
    assert "bounce_rate" in result["imminent_thresholds"]


def test_forecast_observes_improving_health():
    result = forecast_reputation_health([
        {"bounce_rate": 0.020, "inbox_placement_rate": 0.92},
        {"bounce_rate": 0.015, "inbox_placement_rate": 0.94},
        {"bounce_rate": 0.010, "inbox_placement_rate": 0.96},
    ])
    assert result["posture"] == "OBSERVE"


def test_forecast_requires_history():
    result = forecast_reputation_health([{"bounce_rate": 0.01}])
    assert result["posture"] == "INSUFFICIENT_HISTORY"
