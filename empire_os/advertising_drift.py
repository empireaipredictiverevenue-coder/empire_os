"""Phase 9 creative economics drift review from observed ad evidence."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Sequence

from empire_os.advertising_brain import AdPerformanceObservation
from empire_os.advertising_freshness import review_advertising_evidence


@dataclass(frozen=True)
class CreativeEconomicsDrift:
    creative_id: str
    baseline_roas: float | None
    current_roas: float | None
    roas_delta: float | None
    baseline_profit_roas: float | None
    current_profit_roas: float | None
    profit_roas_delta: float | None
    direction: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AdvertisingDriftReview:
    campaign_id: str
    comparison_available: bool
    creative_drift: tuple[CreativeEconomicsDrift, ...]
    blockers: tuple[str, ...]
    execution_authority: str = "none"
    campaign_creation: bool = False
    budget_mutation: bool = False
    pause_mutation: bool = False
    retarget_execution: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "creative_drift": [row.as_dict() for row in self.creative_drift],
        }



def review_advertising_drift(
    *,
    baseline: Sequence[AdPerformanceObservation],
    current: Sequence[AdPerformanceObservation],
    campaign_id: str,
    now: datetime,
    max_age_seconds: int = 21600,
) -> AdvertisingDriftReview:
    baseline_review = review_advertising_evidence(
        baseline,
        campaign_id=campaign_id,
        now=now,
        max_age_seconds=max_age_seconds,
    )
    current_review = review_advertising_evidence(
        current,
        campaign_id=campaign_id,
        now=now,
        max_age_seconds=max_age_seconds,
    )

    blockers = [
        f"baseline:{item}" for item in baseline_review.blockers
    ]
    blockers.extend(
        f"current:{item}" for item in current_review.blockers
    )
    if not baseline_review.fresh_for_review:
        blockers.append("baseline_evidence_not_fresh")
    if not current_review.fresh_for_review:
        blockers.append("current_evidence_not_fresh")

    baseline_map = {
        row.creative_id: row for row in baseline_review.creatives
    }
    current_map = {
        row.creative_id: row for row in current_review.creatives
    }
    drift: list[CreativeEconomicsDrift] = []
    for creative_id in sorted(set(baseline_map) | set(current_map)):
        before = baseline_map.get(creative_id)
        after = current_map.get(creative_id)
        if before is None or after is None:
            blockers.append(
                f"creative_{creative_id}_comparison_evidence_missing"
            )
            continue
        if not before.attribution_complete or not after.attribution_complete:
            blockers.append(
                f"creative_{creative_id}_attribution_incomplete"
            )
            continue

        roas_delta = (
            after.roas - before.roas
            if before.roas is not None and after.roas is not None
            else None
        )
        profit_delta = (
            after.profit_roas - before.profit_roas
            if (
                before.profit_roas is not None
                and after.profit_roas is not None
            )
            else None
        )
        direction = "unknown"
        if profit_delta is not None:
            if abs(profit_delta) <= 1e-12:
                direction = "stable"
            elif profit_delta > 0:
                direction = "improving"
            else:
                direction = "declining"

        drift.append(CreativeEconomicsDrift(
            creative_id=creative_id,
            baseline_roas=before.roas,
            current_roas=after.roas,
            roas_delta=(
                round(roas_delta, 4)
                if roas_delta is not None else None
            ),
            baseline_profit_roas=before.profit_roas,
            current_profit_roas=after.profit_roas,
            profit_roas_delta=(
                round(profit_delta, 4)
                if profit_delta is not None else None
            ),
            direction=direction,
        ))

    ordered = tuple(sorted(set(blockers)))
    return AdvertisingDriftReview(
        campaign_id=campaign_id,
        comparison_available=bool(drift) and not ordered,
        creative_drift=tuple(drift),
        blockers=ordered,
    )
