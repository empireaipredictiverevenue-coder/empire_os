"""Phase 18 typed Revenue OS model-review feedback."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.revenue_os_learning import RevenueOsLearningReadiness


@dataclass(frozen=True)
class RevenueOsModelReviewFeedback:
    packet_key: str
    eligible_for_model_review: bool
    realized_gross_profit_cents: int | None
    profitability_state: str
    outcome_age_seconds: float | None
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


def _profitability_state(value: int | None) -> str:
    if value is None:
        return "unknown"
    if value > 0:
        return "positive_realized_gp"
    if value < 0:
        return "negative_realized_gp"
    return "breakeven_realized_gp"


def build_revenue_os_model_review_feedback(
    readiness: RevenueOsLearningReadiness,
) -> RevenueOsModelReviewFeedback:
    blockers = list(readiness.blockers)
    if not readiness.learning_ready:
        blockers.append("revenue_os_learning_not_ready_for_model_review")

    realized_gp = readiness.feedback.realized_gross_profit_cents
    return RevenueOsModelReviewFeedback(
        packet_key=readiness.packet_key,
        eligible_for_model_review=readiness.learning_ready,
        realized_gross_profit_cents=realized_gp,
        profitability_state=_profitability_state(realized_gp),
        outcome_age_seconds=readiness.outcome_age_seconds,
        blockers=tuple(sorted(set(blockers))),
    )
