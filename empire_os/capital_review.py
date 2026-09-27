"""Phase 15 operator-review controls for capital recommendations."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.capital_allocator import (
    CapitalAssessment,
    CapitalCandidate,
    assess_capital_candidate,
)


@dataclass(frozen=True)
class CapitalReviewPolicy:
    minimum_confidence: float = 0.5
    maximum_downside_ratio: float = 1.0
    minimum_risk_adjusted_score: float = 0.0

    def validate(self) -> None:
        if not 0 <= self.minimum_confidence <= 1:
            raise ValueError("minimum_confidence must be between 0 and 1")
        if self.maximum_downside_ratio < 0:
            raise ValueError("maximum_downside_ratio must be nonnegative")


@dataclass(frozen=True)
class CapitalReview:
    candidate_id: str
    assessment: CapitalAssessment
    review_eligible: bool
    blockers: tuple[str, ...]
    recommendation_only: bool = True
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "assessment": self.assessment.as_dict(),
            "review_eligible": self.review_eligible,
            "blockers": list(self.blockers),
            "recommendation_only": self.recommendation_only,
            "execution_authority": self.execution_authority,
        }


def review_capital_candidate(
    candidate: CapitalCandidate,
    *,
    policy: CapitalReviewPolicy | None = None,
) -> CapitalReview:
    active_policy = policy or CapitalReviewPolicy()
    active_policy.validate()
    candidate.validate()
    assessment = assess_capital_candidate(candidate)

    blockers: list[str] = []
    if candidate.confidence < active_policy.minimum_confidence:
        blockers.append("confidence_below_policy")
    if assessment.downside_ratio > active_policy.maximum_downside_ratio:
        blockers.append("downside_above_policy")
    if (
        assessment.risk_adjusted_score
        < active_policy.minimum_risk_adjusted_score
    ):
        blockers.append("risk_adjusted_score_below_policy")

    return CapitalReview(
        candidate_id=candidate.candidate_id,
        assessment=assessment,
        review_eligible=not blockers,
        blockers=tuple(blockers),
    )
