"""Phase 14 simulation-error feedback packet for model review only."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.digital_twin_calibration import DigitalTwinCalibrationReadiness


@dataclass(frozen=True)
class DigitalTwinModelReviewFeedback:
    scenario_id: str
    eligible_for_model_review: bool
    served_unit_error: int
    served_unit_bias: str
    revenue_error_cents: int | None
    revenue_error_ratio: float | None
    revenue_bias: str
    blockers: tuple[str, ...]
    simulation_only: bool = True
    actual_revenue: bool = False
    execution_authority: str = "none"
    model_weight_mutation: bool = False
    capital_execution: bool = False
    campaign_execution: bool = False
    pricing_execution: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _bias(error: int | float | None) -> str:
    if error is None:
        return "unknown"
    if error > 0:
        return "under_predicted"
    if error < 0:
        return "over_predicted"
    return "on_target"


def build_digital_twin_model_review_feedback(
    calibration: DigitalTwinCalibrationReadiness,
) -> DigitalTwinModelReviewFeedback:
    realization = calibration.realization
    blockers = list(calibration.blockers)
    if not calibration.ready_for_model_review:
        blockers.append("calibration_not_ready_for_model_review")

    return DigitalTwinModelReviewFeedback(
        scenario_id=calibration.scenario_id,
        eligible_for_model_review=calibration.ready_for_model_review,
        served_unit_error=realization.served_unit_error,
        served_unit_bias=_bias(realization.served_unit_error),
        revenue_error_cents=realization.revenue_error_cents,
        revenue_error_ratio=realization.revenue_error_ratio,
        revenue_bias=_bias(realization.revenue_error_cents),
        blockers=tuple(sorted(set(blockers))),
    )
