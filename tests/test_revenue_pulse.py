from empire_os.revenue_pulse import (
    RevenuePulseForecast,
    RevenuePulseWindow,
    SpatialPhysicalPulse,
    StormPulse,
    build_revenue_pulse,
)


def window(**overrides):
    base = dict(
        label="current_24h",
        hours=24,
        acquisitions=20,
        qualified=10,
        buyer_reviews=5,
        delivered_outreach=4,
        commercial_replies=1,
        commercial_terms=0,
        verified_payments=0,
        fulfilments=0,
        recognized_revenue_cents=0,
        realized_gp_cents=0,
        evidence_refs=("canonical:current",),
    )
    base.update(overrides)
    return RevenuePulseWindow(**base)


def test_forecast_and_storm_never_enter_revenue_truth():
    pulse = build_revenue_pulse(
        current=window(),
        forecasts=(
            RevenuePulseForecast(
                horizon="30d",
                forecast_revenue_cents=500_000,
                confidence=0.7,
                evidence_refs=("forecast:model:v1",),
                model_key="forecast_v1",
            ),
        ),
        storm=StormPulse(
            opportunity_count=8,
            max_multiplier=2.454,
            priority_boost_max=36.35,
            evidence_refs=("nws:dfw:2026-09-20",),
        ),
    )

    truth = pulse["recognized_revenue_truth"]
    assert truth["recognized_revenue_cents"] == 0
    assert truth["realized_gp_cents"] == 0
    assert truth["forecast_included_in_truth"] is False
    assert pulse["forecast"]["items"][0]["forecast_revenue_cents"] == 500_000
    assert pulse["storm_pulse"]["max_multiplier"] == 2.454


def test_spatial_physical_pulse_stays_outside_revenue_truth():
    pulse = build_revenue_pulse(
        current=window(),
        spatial_physical=SpatialPhysicalPulse(
            volumetric_observations=4,
            physical_observations=3,
            modeled_opportunities=2,
            max_combined_priority_boost=48.2,
            evidence_refs=("spatial:batch:1", "physical:batch:1"),
        ),
    )

    assert pulse["spatial_physical_pulse"]["modeled_opportunities"] == 2
    assert pulse["recognized_revenue_truth"]["recognized_revenue_cents"] == 0
    assert pulse["recognized_revenue_truth"]["forecast_included_in_truth"] is False
    assert "spatial:batch:1" in pulse["evidence_refs"]


def test_conversion_and_blocker_state_are_evidence_backed():
    pulse = build_revenue_pulse(
        current=window(),
        highest_priority_blocker="buyer_conversation",
        blocker_state="blocked",
    )

    assert pulse["pulse_state"] == "commercial_conversation_active"
    assert pulse["conversion"]["acquisition_to_qualified"] == 0.5
    assert pulse["conversion"]["buyer_review_to_delivered_outreach"] == 0.8
    assert pulse["conversion"]["commercial_reply_to_terms"] == 0.0
    assert pulse["highest_priority_blocker"] == "buyer_conversation"


def test_zero_to_positive_velocity_is_new_activity_not_infinite_growth():
    current = window(delivered_outreach=4)
    previous = window(
        label="previous_24h",
        delivered_outreach=0,
        commercial_replies=0,
        evidence_refs=("canonical:previous",),
    )

    pulse = build_revenue_pulse(
        current=current,
        previous=previous,
    )

    delivered = pulse["velocity"]["delivered_outreach"]
    assert delivered["state"] == "new_activity"
    assert delivered["absolute_change"] == 4
    assert delivered["pct_change"] is None


def test_missing_counts_remain_unknown():
    pulse = build_revenue_pulse(
        current=window(
            qualified=None,
            buyer_reviews=None,
        ),
    )

    assert pulse["conversion"]["acquisition_to_qualified"] is None
    assert pulse["conversion"]["qualified_to_buyer_review"] is None
    assert pulse["unknown_stays_unknown"] is True


def test_window_requires_evidence():
    bad = window(evidence_refs=())

    try:
        build_revenue_pulse(current=bad)
    except ValueError as exc:
        assert "pulse window evidence required" in str(exc)
    else:
        raise AssertionError("pulse must require evidence")



def test_zero_conversion_leak_is_observed_not_predicted():
    pulse = build_revenue_pulse(
        current=window(
            delivered_outreach=5,
            commercial_replies=0,
            commercial_terms=0,
        ),
    )

    leaks = pulse["leak_detection"]["items"]
    assert pulse["leak_detection"]["prediction"] is False
    assert any(
        item["from_stage"] == "delivered_outreach"
        and item["to_stage"] == "commercial_replies"
        and item["state"] == "observed_zero_conversion"
        and item["prediction"] is False
        for item in leaks
    )
    assert any(
        alert["stage"] == "commercial_replies"
        and alert["prediction"] is False
        for alert in pulse["alerts"]
    )
