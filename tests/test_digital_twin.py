import pytest

from empire_os.digital_twin import (
    MarketBaseline,
    MarketScenario,
    simulate_market_scenario,
)


def baseline():
    return MarketBaseline(
        niche="roofing",
        metro="London",
        observed_demand_units=20,
        observed_capacity_units=10,
        observed_price_per_unit_cents=10000,
        observed_at="2026-09-19T20:30:00+00:00",
        evidence_ref="exchange-observation-1",
    )


def test_scenario_uses_observed_baseline_and_explicit_assumptions():
    result = simulate_market_scenario(
        baseline=baseline(),
        scenario=MarketScenario(
            scenario_id="scenario-1",
            demand_multiplier=1.5,
            capacity_multiplier=2.0,
            price_multiplier=1.1,
        ),
    )
    assert result.projected_demand_units == 30
    assert result.projected_capacity_units == 20
    assert result.projected_served_units == 20
    assert result.projected_price_per_unit_cents == 11000
    assert result.projected_revenue_cents == 220000


def test_simulation_can_never_present_as_actual_revenue():
    result = simulate_market_scenario(
        baseline=baseline(),
        scenario=MarketScenario(scenario_id="scenario-1"),
    )
    assert result.simulation_only is True
    assert result.actual_revenue is False


def test_baseline_requires_provenance():
    bad = MarketBaseline(
        niche="roofing",
        metro="London",
        observed_demand_units=20,
        observed_capacity_units=10,
        observed_price_per_unit_cents=10000,
        observed_at="",
        evidence_ref="",
    )
    with pytest.raises(ValueError, match="provenance"):
        bad.validate()


def test_negative_scenario_multiplier_is_rejected():
    with pytest.raises(ValueError, match="nonnegative"):
        simulate_market_scenario(
            baseline=baseline(),
            scenario=MarketScenario(
                scenario_id="scenario-1",
                demand_multiplier=-1,
            ),
        )
