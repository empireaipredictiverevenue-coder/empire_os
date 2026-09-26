"""Phase 18 OBSERVE-only learning feedback from real outcomes."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class RevenueOsOutcomeEvidence:
    packet_key: str
    outcome_observed: bool
    revenue_recognized: bool
    recognized_revenue_cents: int | None
    observed_cost_cents: int | None
    observed_at: str
    evidence_refs: tuple[str, ...]

    def validate(self) -> None:
        if not self.packet_key.strip():
            raise ValueError("packet_key required")
        if (
            self.recognized_revenue_cents is not None
            and self.recognized_revenue_cents < 0
        ):
            raise ValueError("recognized_revenue_cents must be nonnegative")
        if self.observed_cost_cents is not None and self.observed_cost_cents < 0:
            raise ValueError("observed_cost_cents must be nonnegative")
        if self.revenue_recognized and self.recognized_revenue_cents is None:
            raise ValueError("recognized revenue amount required")
        if (
            not self.revenue_recognized
            and self.recognized_revenue_cents is not None
        ):
            raise ValueError(
                "recognized revenue amount requires revenue_recognized=true"
            )
        if not self.observed_at.strip() or not self.evidence_refs:
            raise ValueError("Revenue OS outcome requires observed provenance")


@dataclass(frozen=True)
class RevenueOsLearningFeedback:
    packet_key: str
    outcome_observed: bool
    revenue_recognized: bool
    recognized_revenue_cents: int | None
    observed_cost_cents: int | None
    realized_gross_profit_cents: int | None
    learning_evidence_complete: bool
    blockers: tuple[str, ...]
    mode: str = "OBSERVE"
    side_effects: str = "none"
    execution_authority: str = "none"
    model_weight_mutation: bool = False
    capital_reallocation: bool = False
    spend_execution: bool = False
    outreach_execution: bool = False
    payment_execution: bool = False
    allocation_execution: bool = False
    deployment_execution: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def review_revenue_os_outcome(
    evidence: RevenueOsOutcomeEvidence,
) -> RevenueOsLearningFeedback:
    evidence.validate()
    blockers: list[str] = []

    if not evidence.outcome_observed:
        blockers.append("commercial_outcome_evidence_missing")
    if not evidence.revenue_recognized:
        blockers.append("recognized_revenue_evidence_missing")
    if evidence.observed_cost_cents is None:
        blockers.append("observed_cost_evidence_missing")

    realized_profit = None
    if (
        evidence.revenue_recognized
        and evidence.recognized_revenue_cents is not None
        and evidence.observed_cost_cents is not None
    ):
        realized_profit = (
            evidence.recognized_revenue_cents - evidence.observed_cost_cents
        )

    ordered = tuple(sorted(set(blockers)))
    return RevenueOsLearningFeedback(
        packet_key=evidence.packet_key,
        outcome_observed=evidence.outcome_observed,
        revenue_recognized=evidence.revenue_recognized,
        recognized_revenue_cents=(
            evidence.recognized_revenue_cents
            if evidence.revenue_recognized
            else None
        ),
        observed_cost_cents=evidence.observed_cost_cents,
        realized_gross_profit_cents=realized_profit,
        learning_evidence_complete=not ordered,
        blockers=ordered,
    )
