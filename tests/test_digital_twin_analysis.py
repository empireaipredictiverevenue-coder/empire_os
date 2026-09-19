from empire_os.digital_twin import MarketBaseline, MarketScenario
from empire_os.digital_twin_analysis import compare_market_scenario


def baseline(demand=20, capacity=10, price=10000):
    return MarketBaseline(
        niche="roofing",
        metro="London",
        observed_demand_units=demand,
        observed_capacity_units=capacity,
        observed_price_per_unit_cents=price,
        observed_at="2026-09-19T23:20:00+00:00",
        evidence_ref="exchange-observation-1",
    )


def test_scenario_delta_is_relative_to_observed_baseline():
    result = compare_market_scenario(
        baseline=baseline(),
        scenario=MarketScenario(
            scenario_id="scenario-1",
            demand_multiplier=1.0,
            capacity_multiplier=2.0,
            price_multiplier=1.0,
        ),
    )
    assert result.baseline_revenue_cents == 100000
    assert result.scenario.projected_revenue_cents == 200000
    assert result.simulated_revenue_delta_cents == 100000
    assert result.simulated_revenue_delta_ratio == 1.0


def test_simulation_never_becomes_actual_or_executable():
    result = compare_market_scenario(
        baseline=baseline(),
        scenario=MarketScenario(scenario_id="scenario-2"),
    )
    assert result.simulation_only is True
    assert result.actual_revenue is False
    assert result.execution_authority == "none"
    assert result.scenario.simulation_only is True
    assert result.scenario.actual_revenue is False


def test_negative_simulated_delta_is_preserved():
    result = compare_market_scenario(
        baseline=baseline(),
        scenario=MarketScenario(
            scenario_id="scenario-3",
            demand_multiplier=0.5,
            capacity_multiplier=1.0,
            price_multiplier=1.0,
        ),
    )
    assert result.scenario.projected_revenue_cents == 100000
    assert result.simulated_revenue_delta_cents == 0


def test_zero_baseline_revenue_keeps_ratio_unknown():
    result = compare_market_scenario(
        baseline=baseline(demand=0),
        scenario=MarketScenario(
            scenario_id="scenario-4",
            demand_multiplier=2.0,
        ),
    )
    assert result.baseline_revenue_cents == 0
    assert result.simulated_revenue_delta_ratio is None
