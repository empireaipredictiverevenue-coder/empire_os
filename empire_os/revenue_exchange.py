"""Phase 13 Revenue Exchange read-only intelligence foundation."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ExchangeSnapshot:
    niche: str
    metro: str
    qualified_inventory_count: int
    active_buyer_capacity: int
    verified_price_per_lead_cents: tuple[int, ...]
    observed_at: str
    source: str

    @property
    def supply_demand_ratio(self) -> float | None:
        if self.active_buyer_capacity <= 0:
            return None
        return round(
            self.qualified_inventory_count / self.active_buyer_capacity,
            4,
        )

    @property
    def observed_price_floor_cents(self) -> int | None:
        return (
            min(self.verified_price_per_lead_cents)
            if self.verified_price_per_lead_cents
            else None
        )

    @property
    def observed_price_ceiling_cents(self) -> int | None:
        return (
            max(self.verified_price_per_lead_cents)
            if self.verified_price_per_lead_cents
            else None
        )

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["supply_demand_ratio"] = self.supply_demand_ratio
        payload["observed_price_floor_cents"] = self.observed_price_floor_cents
        payload["observed_price_ceiling_cents"] = self.observed_price_ceiling_cents
        return payload
def normalise_exchange_snapshot(
    row: Mapping[str, Any],
) -> ExchangeSnapshot:
    niche = str(row.get("niche") or "").strip()
    metro = str(row.get("metro") or "").strip()
    observed_at = str(row.get("observed_at") or "").strip()
    source = str(row.get("source") or "").strip()
    if not niche or not metro or not observed_at or not source:
        raise ValueError("niche, metro, observed_at and source are required")

    inventory = int(row.get("qualified_inventory_count") or 0)
    capacity = int(row.get("active_buyer_capacity") or 0)
    if inventory < 0 or capacity < 0:
        raise ValueError("inventory and capacity must be nonnegative")

    prices = tuple(
        int(value)
        for value in (row.get("verified_price_per_lead_cents") or ())
    )
    if any(value <= 0 for value in prices):
        raise ValueError("verified prices must be positive")

    return ExchangeSnapshot(
        niche=niche,
        metro=metro,
        qualified_inventory_count=inventory,
        active_buyer_capacity=capacity,
        verified_price_per_lead_cents=prices,
        observed_at=observed_at,
        source=source,
    )
