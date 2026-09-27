"""Phase 14 simulation comparison for Digital Twin."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.digital_twin import (
    MarketBaseline,
    MarketScenario,
    MarketScenarioResult,
    simulate_market_scenario,
)


@dataclass(frozen=True)
class ScenarioComparison:
    baseline_revenue_cents: int
    scenario: MarketScenarioResult
    simulated_revenue_delta_cents: int
    simulated_revenue_delta_ratio: float | None
    simulation_only: bool = True
    actual_revenue: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return {
            "baseline_revenue_cents": self.baseline_revenue_cents,
            "scenario": self.scenario.as_dict(),
            "simulated_revenue_delta_cents": self.simulated_revenue_delta_cents,
            "simulated_revenue_delta_ratio": self.simulated_revenue_delta_ratio,
            "simulation_only": self.simulation_only,
            "actual_revenue": self.actual_revenue,
            "execution_authority": self.execution_authority,
        }


def compare_market_scenario(
    *,
    baseline: MarketBaseline,
    scenario: MarketScenario,
) -> ScenarioComparison:
    baseline.validate()
    scenario_result = simulate_market_scenario(
        baseline=baseline,
        scenario=scenario,
    )

    baseline_served = min(
        baseline.observed_demand_units,
        baseline.observed_capacity_units,
    )
    baseline_revenue = (
        baseline_served * baseline.observed_price_per_unit_cents
    )
    delta = scenario_result.projected_revenue_cents - baseline_revenue
    ratio = None if baseline_revenue == 0 else delta / baseline_revenue

    return ScenarioComparison(
        baseline_revenue_cents=baseline_revenue,
        scenario=scenario_result,
        simulated_revenue_delta_cents=delta,
        simulated_revenue_delta_ratio=(
            round(ratio, 4) if ratio is not None else None
        ),
    )
