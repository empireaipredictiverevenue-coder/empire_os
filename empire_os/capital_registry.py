"""Governed Phase 15 capital review registry contract."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from empire_os.capital_allocator import CapitalCandidate
from empire_os.capital_review import CapitalReview, CapitalReviewPolicy


@dataclass(frozen=True)
class CapitalReviewRecord:
    review_key: str
    candidate: CapitalCandidate
    policy: CapitalReviewPolicy
    review: CapitalReview
    evidence: Mapping[str, Any]

    def validate(self) -> None:
        if not str(self.review_key or "").strip():
            raise ValueError("review_key required")
        self.candidate.validate()
        self.policy.validate()
        if self.review.candidate_id != self.candidate.candidate_id:
            raise ValueError("capital review candidate mismatch")
        if self.review.recommendation_only is not True:
            raise ValueError("capital registry requires recommendation_only")
        if self.review.execution_authority != "none":
            raise ValueError("capital registry cannot grant execution authority")
        if not isinstance(self.evidence, Mapping) or not self.evidence:
            raise ValueError("capital registry requires evidence")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "review_key": self.review_key,
            "candidate": {
                "candidate_id": self.candidate.candidate_id,
                "expected_return_cents": self.candidate.expected_return_cents,
                "required_capital_cents": self.candidate.required_capital_cents,
                "downside_loss_cents": self.candidate.downside_loss_cents,
                "confidence": self.candidate.confidence,
                "time_to_revenue_days": self.candidate.time_to_revenue_days,
                "evidence_refs": list(self.candidate.evidence_refs),
            },
            "policy": {
                "minimum_confidence": self.policy.minimum_confidence,
                "maximum_downside_ratio": self.policy.maximum_downside_ratio,
                "minimum_risk_adjusted_score": (
                    self.policy.minimum_risk_adjusted_score
                ),
            },
            "review": self.review.as_dict(),
            "evidence": dict(self.evidence),
            "mode": "OBSERVE",
            "recommendation_only": True,
            "execution_authority": "none",
            "funds_movement": False,
            "budget_mutation": False,
        }
