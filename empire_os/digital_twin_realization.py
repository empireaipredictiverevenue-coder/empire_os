"""Phase 14 observed realization review for Digital Twin."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.digital_twin import MarketScenarioResult


@dataclass(frozen=True)
class ObservedMarketOutcome:
    observed_served_units: int
    observed_revenue_cents: int | None
    revenue_recognized: bool
    observed_at: str
    evidence_refs: tuple[str, ...]

    def validate(self) -> None:
        if self.observed_served_units < 0:
            raise ValueError("observed_served_units must be nonnegative")
        if self.observed_revenue_cents is not None:
            if self.observed_revenue_cents < 0:
                raise ValueError("observed_revenue_cents must be nonnegative")
        if self.revenue_recognized and self.observed_revenue_cents is None:
            raise ValueError("recognized revenue amount required")
        if not self.observed_at.strip() or not self.evidence_refs:
            raise ValueError("observed outcome provenance required")


@dataclass(frozen=True)
class ScenarioRealizationReview:
    scenario_id: str
    projected_served_units: int
    observed_served_units: int
    served_unit_error: int
    projected_revenue_cents: int
    observed_revenue_cents: int | None
    revenue_error_cents: int | None
    revenue_error_ratio: float | None
    revenue_comparison_available: bool
    blockers: tuple[str, ...]
    simulation_only: bool = True
    creates_actual_revenue: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def review_scenario_realization(
    *,
    scenario: MarketScenarioResult,
    observed: ObservedMarketOutcome,
) -> ScenarioRealizationReview:
    observed.validate()
    blockers: list[str] = []
    revenue_error = None
    revenue_ratio = None
    revenue_available = (
        observed.revenue_recognized
        and observed.observed_revenue_cents is not None
    )
    if revenue_available:
        revenue_error = (
            observed.observed_revenue_cents
            - scenario.projected_revenue_cents
        )
        if scenario.projected_revenue_cents > 0:
            revenue_ratio = (
                revenue_error / scenario.projected_revenue_cents
            )
    else:
        blockers.append("recognized_revenue_evidence_missing")

    return ScenarioRealizationReview(
        scenario_id=scenario.scenario_id,
        projected_served_units=scenario.projected_served_units,
        observed_served_units=observed.observed_served_units,
        served_unit_error=(
            observed.observed_served_units
            - scenario.projected_served_units
        ),
        projected_revenue_cents=scenario.projected_revenue_cents,
        observed_revenue_cents=(
            observed.observed_revenue_cents
            if revenue_available
            else None
        ),
        revenue_error_cents=revenue_error,
        revenue_error_ratio=(
            round(revenue_ratio, 4)
            if revenue_ratio is not None
            else None
        ),
        revenue_comparison_available=revenue_available,
        blockers=tuple(blockers),
    )
