"""Phase 12 observed demand outcome feedback."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class DemandOutcomeEvidence:
    plan_id: str
    success_metric: str
    baseline_value: float | None
    observed_value: float | None
    observed_cost_cents: int | None
    observed_at: str
    evidence_refs: tuple[str, ...]

    def validate(self) -> None:
        if not self.plan_id.strip() or not self.success_metric.strip():
            raise ValueError("plan_id and success_metric required")
        if self.observed_cost_cents is not None and self.observed_cost_cents < 0:
            raise ValueError("observed_cost_cents must be nonnegative")
        if not self.observed_at.strip() or not self.evidence_refs:
            raise ValueError("demand outcome requires observed provenance")


@dataclass(frozen=True)
class DemandOutcomeReview:
    plan_id: str
    success_metric: str
    outcome_available: bool
    baseline_value: float | None
    observed_value: float | None
    absolute_change: float | None
    relative_change: float | None
    observed_cost_cents: int | None
    blockers: tuple[str, ...]
    execution_authority: str = "none"
    publishing_enabled: bool = False
    outbound_enabled: bool = False
    ad_spend_enabled: bool = False
    provider_activation_enabled: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def review_demand_outcome(
    evidence: DemandOutcomeEvidence,
) -> DemandOutcomeReview:
    evidence.validate()

    blockers: list[str] = []
    available = (
        evidence.baseline_value is not None
        and evidence.observed_value is not None
    )
    if not available:
        blockers.append("success_metric_outcome_evidence_incomplete")

    absolute = None
    relative = None
    if available:
        absolute = evidence.observed_value - evidence.baseline_value
        if evidence.baseline_value != 0:
            relative = absolute / evidence.baseline_value

    return DemandOutcomeReview(
        plan_id=evidence.plan_id,
        success_metric=evidence.success_metric,
        outcome_available=available,
        baseline_value=evidence.baseline_value,
        observed_value=evidence.observed_value,
        absolute_change=(
            round(absolute, 4) if absolute is not None else None
        ),
        relative_change=(
            round(relative, 4) if relative is not None else None
        ),
        observed_cost_cents=evidence.observed_cost_cents,
        blockers=tuple(blockers),
    )
