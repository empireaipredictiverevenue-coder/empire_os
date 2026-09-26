"""Phase 15 realized-return feedback for capital recommendations."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class CapitalOutcomeEvidence:
    candidate_id: str
    expected_return_cents: int
    required_capital_cents: int
    recognized_revenue_cents: int | None
    observed_cost_cents: int | None
    observed_at: str
    evidence_refs: tuple[str, ...]

    def validate(self) -> None:
        if not self.candidate_id.strip():
            raise ValueError("candidate_id required")
        if self.expected_return_cents < 0:
            raise ValueError("expected_return_cents must be nonnegative")
        if self.required_capital_cents <= 0:
            raise ValueError("required_capital_cents must be positive")
        if (
            self.recognized_revenue_cents is not None
            and self.recognized_revenue_cents < 0
        ):
            raise ValueError("recognized_revenue_cents must be nonnegative")
        if self.observed_cost_cents is not None and self.observed_cost_cents < 0:
            raise ValueError("observed_cost_cents must be nonnegative")
        if not self.observed_at.strip() or not self.evidence_refs:
            raise ValueError("capital outcome requires observed provenance")


@dataclass(frozen=True)
class CapitalOutcomeReview:
    candidate_id: str
    outcome_available: bool
    expected_return_cents: int
    realized_gross_profit_cents: int | None
    expected_vs_realized_delta_cents: int | None
    realized_return_multiple: float | None
    blockers: tuple[str, ...]
    execution_authority: str = "none"
    funds_movement: bool = False
    budget_mutation: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def review_capital_outcome(
    evidence: CapitalOutcomeEvidence,
) -> CapitalOutcomeReview:
    evidence.validate()

    blockers: list[str] = []
    available = (
        evidence.recognized_revenue_cents is not None
        and evidence.observed_cost_cents is not None
    )
    realized_profit = None
    delta = None
    multiple = None

    if available:
        realized_profit = (
            evidence.recognized_revenue_cents
            - evidence.observed_cost_cents
        )
        delta = realized_profit - evidence.expected_return_cents
        multiple = realized_profit / evidence.required_capital_cents
    else:
        blockers.append("recognized_revenue_or_cost_evidence_missing")

    return CapitalOutcomeReview(
        candidate_id=evidence.candidate_id,
        outcome_available=available,
        expected_return_cents=evidence.expected_return_cents,
        realized_gross_profit_cents=realized_profit,
        expected_vs_realized_delta_cents=delta,
        realized_return_multiple=(
            round(multiple, 4) if multiple is not None else None
        ),
        blockers=tuple(blockers),
    )
