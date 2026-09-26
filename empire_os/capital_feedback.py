"""Phase 15 capital calibration feedback for model review only."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.capital_freshness import CapitalOutcomeCalibration


@dataclass(frozen=True)
class CapitalModelReviewFeedback:
    candidate_id: str
    eligible_for_model_review: bool
    expected_return_multiple: float
    realized_return_multiple: float | None
    return_multiple_error: float | None
    expectation_bias: str
    realized_gross_profit_cents: int | None
    blockers: tuple[str, ...]
    recommendation_only: bool = True
    execution_authority: str = "none"
    model_weight_mutation: bool = False
    recommendation_mutation: bool = False
    funds_movement: bool = False
    budget_mutation: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _bias(error: float | None) -> str:
    if error is None:
        return "unknown"
    if error > 0:
        return "under_estimated_return"
    if error < 0:
        return "over_estimated_return"
    return "on_target"


def build_capital_model_review_feedback(
    calibration: CapitalOutcomeCalibration,
) -> CapitalModelReviewFeedback:
    blockers = list(calibration.blockers)
    if not calibration.calibration_available:
        blockers.append("capital_calibration_not_ready_for_model_review")

    return CapitalModelReviewFeedback(
        candidate_id=calibration.candidate_id,
        eligible_for_model_review=calibration.calibration_available,
        expected_return_multiple=calibration.expected_return_multiple,
        realized_return_multiple=calibration.realized_return_multiple,
        return_multiple_error=calibration.return_multiple_error,
        expectation_bias=_bias(calibration.return_multiple_error),
        realized_gross_profit_cents=calibration.realized_gross_profit_cents,
        blockers=tuple(sorted(set(blockers))),
    )
