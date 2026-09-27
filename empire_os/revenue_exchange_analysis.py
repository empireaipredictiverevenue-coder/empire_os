"""Phase 13 read-only market balance analysis for Revenue Exchange."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.revenue_exchange import ExchangeSnapshot


@dataclass(frozen=True)
class ExchangeMarketAssessment:
    niche: str
    metro: str
    market_state: str
    supply_demand_ratio: float | None
    observed_price_floor_cents: int | None
    observed_price_ceiling_cents: int | None
    review_reason: str
    allocation_authority: str = "none"
    settlement_authority: str = "none"
    pricing_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_exchange_market(
    snapshot: ExchangeSnapshot,
) -> ExchangeMarketAssessment:
    ratio = snapshot.supply_demand_ratio
    if snapshot.active_buyer_capacity <= 0:
        state = "no_verified_capacity"
        reason = "buyer_capacity_missing_or_zero"
    elif snapshot.qualified_inventory_count <= 0:
        state = "no_qualified_inventory"
        reason = "qualified_inventory_missing_or_zero"
    elif ratio is None:
        state = "unknown"
        reason = "supply_demand_ratio_unavailable"
    elif ratio > 1.25:
        state = "inventory_heavy"
        reason = "qualified_inventory_exceeds_observed_buyer_capacity"
    elif ratio < 0.75:
        state = "capacity_heavy"
        reason = "observed_buyer_capacity_exceeds_qualified_inventory"
    else:
        state = "balanced_observed_range"
        reason = "observed_inventory_and_capacity_are_within_balance_band"

    return ExchangeMarketAssessment(
        niche=snapshot.niche,
        metro=snapshot.metro,
        market_state=state,
        supply_demand_ratio=ratio,
        observed_price_floor_cents=snapshot.observed_price_floor_cents,
        observed_price_ceiling_cents=snapshot.observed_price_ceiling_cents,
        review_reason=reason,
    )
