"""Phase 9 evidence-backed campaign economics review."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

from empire_os.advertising_brain import AdPerformanceObservation


@dataclass(frozen=True)
class CampaignEconomicsReview:
    campaign_id: str
    observation_count: int
    total_spend_cents: int
    total_conversions: int | None
    total_attributed_revenue_cents: int | None
    total_attributed_gross_profit_cents: int | None
    roas: float | None
    profit_roas: float | None
    attribution_complete: bool
    review_state: str
    blockers: tuple[str, ...]
    execution_authority: str = "none"
    budget_mutation: bool = False
    pause_mutation: bool = False
    retarget_execution: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def review_campaign_economics(
    observations: Sequence[AdPerformanceObservation],
    *,
    campaign_id: str,
) -> CampaignEconomicsReview:
    cid = str(campaign_id or "").strip()
    if not cid:
        raise ValueError("campaign_id required")
    rows = tuple(observations)
    if any(row.campaign_id != cid for row in rows):
        raise ValueError("campaign review contains mixed campaign ids")

    spend = sum(row.spend_cents for row in rows)
    conversions_known = all(
        row.conversions is not None for row in rows
    )
    revenue_known = all(
        row.attributed_revenue_cents is not None for row in rows
    )
    profit_known = all(
        row.attributed_gross_profit_cents is not None for row in rows
    )

    total_conversions = (
        sum(int(row.conversions or 0) for row in rows)
        if rows and conversions_known
        else None
    )
    total_revenue = (
        sum(int(row.attributed_revenue_cents or 0) for row in rows)
        if rows and revenue_known
        else None
    )
    total_profit = (
        sum(int(row.attributed_gross_profit_cents or 0) for row in rows)
        if rows and profit_known
        else None
    )
    roas = (
        total_revenue / spend
        if spend > 0 and total_revenue is not None
        else None
    )
    profit_roas = (
        total_profit / spend
        if spend > 0 and total_profit is not None
        else None
    )

    blockers: list[str] = []
    if not rows:
        blockers.append("campaign_observations_missing")
    if rows and not revenue_known:
        blockers.append("revenue_attribution_incomplete")
    if rows and not profit_known:
        blockers.append("gross_profit_attribution_incomplete")

    attribution_complete = bool(rows) and revenue_known and profit_known
    review_state = (
        "evidence_complete_for_operator_review"
        if attribution_complete
        else "insufficient_attribution_evidence"
    )

    return CampaignEconomicsReview(
        campaign_id=cid,
        observation_count=len(rows),
        total_spend_cents=spend,
        total_conversions=total_conversions,
        total_attributed_revenue_cents=total_revenue,
        total_attributed_gross_profit_cents=total_profit,
        roas=round(roas, 4) if roas is not None else None,
        profit_roas=(
            round(profit_roas, 4)
            if profit_roas is not None
            else None
        ),
        attribution_complete=attribution_complete,
        review_state=review_state,
        blockers=tuple(blockers),
    )
