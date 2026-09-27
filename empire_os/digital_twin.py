"""Phase 14 Digital Twin deterministic scenario foundation."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class MarketBaseline:
    niche: str
    metro: str
    observed_demand_units: int
    observed_capacity_units: int
    observed_price_per_unit_cents: int
    observed_at: str
    evidence_ref: str

    def validate(self) -> None:
        if not self.niche.strip() or not self.metro.strip():
            raise ValueError("baseline market identity required")
        if self.observed_demand_units < 0 or self.observed_capacity_units < 0:
            raise ValueError("baseline units must be nonnegative")
        if self.observed_price_per_unit_cents <= 0:
            raise ValueError("baseline observed price must be positive")
        if not self.observed_at.strip() or not self.evidence_ref.strip():
            raise ValueError("baseline provenance required")


@dataclass(frozen=True)
class MarketScenario:
    scenario_id: str
    demand_multiplier: float = 1.0
    capacity_multiplier: float = 1.0
    price_multiplier: float = 1.0

    def validate(self) -> None:
        if not self.scenario_id.strip():
            raise ValueError("scenario_id required")
        for name, value in (
            ("demand_multiplier", self.demand_multiplier),
            ("capacity_multiplier", self.capacity_multiplier),
            ("price_multiplier", self.price_multiplier),
        ):
            if value < 0:
                raise ValueError(f"{name} must be nonnegative")
@dataclass(frozen=True)
class MarketScenarioResult:
    scenario_id: str
    projected_demand_units: int
    projected_capacity_units: int
    projected_served_units: int
    projected_price_per_unit_cents: int
    projected_revenue_cents: int
    simulation_only: bool = True
    actual_revenue: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def simulate_market_scenario(
    *,
    baseline: MarketBaseline,
    scenario: MarketScenario,
) -> MarketScenarioResult:
    baseline.validate()
    scenario.validate()

    projected_demand = round(
        baseline.observed_demand_units * scenario.demand_multiplier
    )
    projected_capacity = round(
        baseline.observed_capacity_units * scenario.capacity_multiplier
    )
    projected_price = round(
        baseline.observed_price_per_unit_cents * scenario.price_multiplier
    )
    served = min(projected_demand, projected_capacity)
    projected_revenue = served * projected_price

    return MarketScenarioResult(
        scenario_id=scenario.scenario_id,
        projected_demand_units=max(projected_demand, 0),
        projected_capacity_units=max(projected_capacity, 0),
        projected_served_units=max(served, 0),
        projected_price_per_unit_cents=max(projected_price, 0),
        projected_revenue_cents=max(projected_revenue, 0),
    )
