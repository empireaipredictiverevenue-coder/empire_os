"""Phase 4 explainable, non-executing Astra intelligence-route review."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.astra import (
    PREMIUM_MIN_ROI_MULTIPLE,
    AstraSnapshot,
    route_intelligence,
)


@dataclass(frozen=True)
class AstraIntelligenceRouteReview:
    task_kind: str
    selected_route: str
    premium_eligible: bool
    expected_value_cents: int
    premium_cost_cents: int
    premium_budget_cents: int
    premium_budget_headroom_cents: int | None
    expected_value_multiple: float | None
    minimum_premium_roi_multiple: int
    blockers: tuple[str, ...]
    mode: str = "OBSERVE"
    side_effects: str = "none"
    execution_authority: str = "none"
    provider_activation: bool = False
    premium_spend_execution: bool = False
    budget_mutation: bool = False
    model_promotion: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def review_intelligence_route(
    snapshot: AstraSnapshot,
    *,
    task_kind: str,
    expected_value_cents: int = 0,
    premium_cost_cents: int = 0,
) -> AstraIntelligenceRouteReview:
    if expected_value_cents < 0:
        raise ValueError("expected_value_cents must be nonnegative")
    if premium_cost_cents < 0:
        raise ValueError("premium_cost_cents must be nonnegative")

    kind = str(task_kind or "routine").strip().lower() or "routine"
    selected = route_intelligence(
        snapshot,
        task_kind=kind,
        expected_value_cents=expected_value_cents,
        premium_cost_cents=premium_cost_cents,
    )

    blockers: list[str] = []
    if kind in {"routine", "structured", "scoring", "matching"}:
        blockers.append("task_bounded_to_rules")
    elif kind in {"language", "classification", "summary", "copy"}:
        blockers.append("task_bounded_to_local")
    else:
        if snapshot.actual_revenue_cents <= 0:
            blockers.append("actual_revenue_evidence_required_for_premium")
        if snapshot.premium_ai_budget_cents <= 0:
            blockers.append("premium_ai_budget_unavailable")
        if premium_cost_cents <= 0:
            blockers.append("premium_cost_required")
        elif premium_cost_cents > snapshot.premium_ai_budget_cents:
            blockers.append("premium_cost_exceeds_budget")
        if (
            premium_cost_cents > 0
            and expected_value_cents
            < premium_cost_cents * PREMIUM_MIN_ROI_MULTIPLE
        ):
            blockers.append("expected_value_below_premium_roi_hurdle")

    value_multiple = None
    if premium_cost_cents > 0:
        value_multiple = round(
            expected_value_cents / premium_cost_cents,
            4,
        )

    budget_headroom = None
    if snapshot.premium_ai_budget_cents >= 0 and premium_cost_cents > 0:
        budget_headroom = max(
            snapshot.premium_ai_budget_cents - premium_cost_cents,
            0,
        )

    return AstraIntelligenceRouteReview(
        task_kind=kind,
        selected_route=selected,
        premium_eligible=(selected == "premium"),
        expected_value_cents=expected_value_cents,
        premium_cost_cents=premium_cost_cents,
        premium_budget_cents=snapshot.premium_ai_budget_cents,
        premium_budget_headroom_cents=budget_headroom,
        expected_value_multiple=value_multiple,
        minimum_premium_roi_multiple=PREMIUM_MIN_ROI_MULTIPLE,
        blockers=tuple(sorted(set(blockers))),
    )
