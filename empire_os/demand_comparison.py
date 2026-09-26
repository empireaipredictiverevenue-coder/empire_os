"""Phase 12 evidence-only comparison of realized Demand Genesis plans."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.demand_freshness import DemandOutcomeEvidenceReview


@dataclass(frozen=True)
class DemandPlanComparison:
    left_plan_id: str
    right_plan_id: str
    success_metric: str
    comparison_available: bool
    absolute_change_delta: float | None
    cost_per_incremental_unit_delta_cents: float | None
    blockers: tuple[str, ...]
    execution_authority: str = "none"
    publishing_enabled: bool = False
    outbound_enabled: bool = False
    ad_spend_enabled: bool = False
    provider_activation_enabled: bool = False
    automatic_plan_selection: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def compare_demand_plan_outcomes(
    left: DemandOutcomeEvidenceReview,
    right: DemandOutcomeEvidenceReview,
) -> DemandPlanComparison:
    blockers: list[str] = []

    if left.plan_id == right.plan_id:
        blockers.append("distinct_plan_ids_required")
    if left.success_metric != right.success_metric:
        blockers.append("success_metric_mismatch")
    if not left.review_ready:
        blockers.append("left_plan_outcome_not_review_ready")
        blockers.extend(f"left:{item}" for item in left.blockers)
    if not right.review_ready:
        blockers.append("right_plan_outcome_not_review_ready")
        blockers.extend(f"right:{item}" for item in right.blockers)

    absolute_delta = None
    efficiency_delta = None
    if (
        left.absolute_change is not None
        and right.absolute_change is not None
        and left.success_metric == right.success_metric
    ):
        absolute_delta = round(
            right.absolute_change - left.absolute_change,
            4,
        )

    if (
        left.cost_efficiency_available
        and right.cost_efficiency_available
        and left.cost_per_incremental_unit_cents is not None
        and right.cost_per_incremental_unit_cents is not None
    ):
        efficiency_delta = round(
            right.cost_per_incremental_unit_cents
            - left.cost_per_incremental_unit_cents,
            4,
        )
    else:
        blockers.append("comparable_cost_efficiency_unavailable")

    ordered = tuple(sorted(set(blockers)))
    return DemandPlanComparison(
        left_plan_id=left.plan_id,
        right_plan_id=right.plan_id,
        success_metric=left.success_metric,
        comparison_available=not ordered,
        absolute_change_delta=absolute_delta if not ordered else None,
        cost_per_incremental_unit_delta_cents=(
            efficiency_delta if not ordered else None
        ),
        blockers=ordered,
    )
