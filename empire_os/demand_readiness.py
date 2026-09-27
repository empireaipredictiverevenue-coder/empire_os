"""Phase 12 evidence-backed demand-plan readiness analysis."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class DemandEvidenceSnapshot:
    plan_id: str
    observed_demand_signals: int
    verified_audience_size: int | None
    qualified_inbound_events: int
    historical_conversion_rate: float | None
    observed_cost_cents: int | None
    evidence_refs: tuple[str, ...]

    def validate(self) -> None:
        if not self.plan_id.strip():
            raise ValueError("plan_id required")
        if self.observed_demand_signals < 0:
            raise ValueError("observed_demand_signals must be nonnegative")
        if (
            self.verified_audience_size is not None
            and self.verified_audience_size < 0
        ):
            raise ValueError("verified_audience_size must be nonnegative")
        if self.qualified_inbound_events < 0:
            raise ValueError("qualified_inbound_events must be nonnegative")
        if (
            self.historical_conversion_rate is not None
            and not 0 <= self.historical_conversion_rate <= 1
        ):
            raise ValueError(
                "historical_conversion_rate must be between 0 and 1"
            )
        if self.observed_cost_cents is not None and self.observed_cost_cents < 0:
            raise ValueError("observed_cost_cents must be nonnegative")
        if not self.evidence_refs:
            raise ValueError("demand readiness requires evidence")


@dataclass(frozen=True)
class DemandReadiness:
    plan_id: str
    ready_for_review: bool
    evidence_score: float
    readiness_reason: str
    missing_evidence: tuple[str, ...]
    execution_authority: str = "none"
    approval_required: bool = True

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
def assess_demand_readiness(
    snapshot: DemandEvidenceSnapshot,
) -> DemandReadiness:
    snapshot.validate()

    missing: list[str] = []
    if snapshot.observed_demand_signals <= 0:
        missing.append("observed_demand_signals")
    if snapshot.verified_audience_size is None:
        missing.append("verified_audience_size")
    if snapshot.historical_conversion_rate is None:
        missing.append("historical_conversion_rate")
    if snapshot.observed_cost_cents is None:
        missing.append("observed_cost_cents")

    evidence_score = 0.0
    if snapshot.observed_demand_signals > 0:
        evidence_score += min(snapshot.observed_demand_signals / 10.0, 1.0) * 0.35
    if snapshot.verified_audience_size is not None:
        evidence_score += min(snapshot.verified_audience_size / 1000.0, 1.0) * 0.20
    if snapshot.qualified_inbound_events > 0:
        evidence_score += min(snapshot.qualified_inbound_events / 10.0, 1.0) * 0.20
    if snapshot.historical_conversion_rate is not None:
        evidence_score += min(snapshot.historical_conversion_rate / 0.2, 1.0) * 0.15
    if snapshot.observed_cost_cents is not None:
        evidence_score += 0.10

    score = round(min(evidence_score, 1.0), 4)
    ready = not missing and score >= 0.5

    if ready:
        reason = "evidence_sufficient_for_operator_review"
    elif missing:
        reason = "required_observed_evidence_missing"
    else:
        reason = "observed_evidence_below_review_threshold"

    return DemandReadiness(
        plan_id=snapshot.plan_id,
        ready_for_review=ready,
        evidence_score=score,
        readiness_reason=reason,
        missing_evidence=tuple(missing),
    )
