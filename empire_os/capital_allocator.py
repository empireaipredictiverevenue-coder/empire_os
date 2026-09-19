"""Phase 15 Capital Allocator recommendation-only foundation."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class CapitalCandidate:
    candidate_id: str
    expected_return_cents: int
    required_capital_cents: int
    downside_loss_cents: int
    confidence: float
    time_to_revenue_days: int
    evidence_refs: tuple[str, ...]

    def validate(self) -> None:
        if not self.candidate_id.strip():
            raise ValueError("candidate_id required")
        if self.expected_return_cents < 0:
            raise ValueError("expected_return_cents must be nonnegative")
        if self.required_capital_cents <= 0:
            raise ValueError("required_capital_cents must be positive")
        if self.downside_loss_cents < 0:
            raise ValueError("downside_loss_cents must be nonnegative")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if self.time_to_revenue_days < 0:
            raise ValueError("time_to_revenue_days must be nonnegative")
        if not self.evidence_refs:
            raise ValueError("capital recommendation requires evidence")


@dataclass(frozen=True)
class CapitalAssessment:
    candidate_id: str
    expected_return_multiple: float
    downside_ratio: float
    time_factor: float
    risk_adjusted_score: float
    recommendation_only: bool = True
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
def assess_capital_candidate(
    candidate: CapitalCandidate,
) -> CapitalAssessment:
    candidate.validate()

    return_multiple = (
        candidate.expected_return_cents
        / candidate.required_capital_cents
    )
    downside_ratio = (
        candidate.downside_loss_cents
        / candidate.required_capital_cents
    )
    time_factor = 1 / (1 + candidate.time_to_revenue_days / 30)
    score = (
        return_multiple
        * candidate.confidence
        * time_factor
        - downside_ratio
    )

    return CapitalAssessment(
        candidate_id=candidate.candidate_id,
        expected_return_multiple=round(return_multiple, 4),
        downside_ratio=round(downside_ratio, 4),
        time_factor=round(time_factor, 4),
        risk_adjusted_score=round(score, 4),
    )


def rank_capital_candidates(
    candidates: list[CapitalCandidate],
) -> list[CapitalAssessment]:
    assessed = [assess_capital_candidate(item) for item in candidates]
    return sorted(
        assessed,
        key=lambda item: (
            -item.risk_adjusted_score,
            item.candidate_id,
        ),
    )
