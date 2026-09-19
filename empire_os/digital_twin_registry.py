"""Governed Phase 14 Digital Twin scenario registry contract."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from empire_os.digital_twin import MarketBaseline, MarketScenario
from empire_os.digital_twin_analysis import ScenarioComparison


@dataclass(frozen=True)
class DigitalTwinRegistryRecord:
    scenario_key: str
    baseline: MarketBaseline
    scenario: MarketScenario
    comparison: ScenarioComparison
    evidence: Mapping[str, Any]

    def validate(self) -> None:
        if not str(self.scenario_key or "").strip():
            raise ValueError("scenario_key required")
        self.baseline.validate()
        self.scenario.validate()
        if self.comparison.scenario.scenario_id != self.scenario.scenario_id:
            raise ValueError("scenario comparison identity mismatch")
        if self.comparison.simulation_only is not True:
            raise ValueError("digital twin registry requires simulation_only")
        if self.comparison.actual_revenue is not False:
            raise ValueError("simulated results cannot be actual revenue")
        if self.comparison.execution_authority != "none":
            raise ValueError("digital twin registry cannot grant execution")
        if not isinstance(self.evidence, Mapping) or not self.evidence:
            raise ValueError("digital twin registry requires evidence")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "scenario_key": self.scenario_key,
            "baseline": {
                "niche": self.baseline.niche,
                "metro": self.baseline.metro,
                "observed_demand_units": self.baseline.observed_demand_units,
                "observed_capacity_units": self.baseline.observed_capacity_units,
                "observed_price_per_unit_cents": (
                    self.baseline.observed_price_per_unit_cents
                ),
                "observed_at": self.baseline.observed_at,
                "evidence_ref": self.baseline.evidence_ref,
            },
            "scenario": {
                "scenario_id": self.scenario.scenario_id,
                "demand_multiplier": self.scenario.demand_multiplier,
                "capacity_multiplier": self.scenario.capacity_multiplier,
                "price_multiplier": self.scenario.price_multiplier,
            },
            "comparison": self.comparison.as_dict(),
            "evidence": dict(self.evidence),
            "mode": "SIMULATION",
            "simulation_only": True,
            "actual_revenue": False,
            "execution_authority": "none",
            "capital_execution": False,
            "campaign_execution": False,
            "pricing_execution": False,
        }
