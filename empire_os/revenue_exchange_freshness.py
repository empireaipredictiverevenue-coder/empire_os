"""Phase 13 Revenue Exchange freshness and market drift review."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from empire_os.revenue_exchange import ExchangeSnapshot
from empire_os.revenue_exchange_reconciliation import ExchangeReconciliation


@dataclass(frozen=True)
class ExchangeFreshness:
    current_age_seconds: float
    baseline_age_seconds: float
    current_freshness: str
    baseline_freshness: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExchangeMarketDrift:
    niche: str
    metro: str
    inventory_delta: int
    buyer_capacity_delta: int
    supply_demand_ratio_delta: float | None
    price_floor_delta_cents: int | None
    price_ceiling_delta_cents: int | None
    verified_price_set_changed: bool | None
    drift_available: bool
    blockers: tuple[str, ...]
    allocation_authority: str = "none"
    pricing_authority: str = "none"
    settlement_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExchangeEvidenceDriftReview:
    freshness: ExchangeFreshness
    reconciliation: ExchangeReconciliation
    drift: ExchangeMarketDrift
    mode: str = "OBSERVE"
    allocation_authority: str = "none"
    pricing_authority: str = "none"
    settlement_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return {
            "freshness": self.freshness.as_dict(),
            "reconciliation": self.reconciliation.as_dict(),
            "drift": self.drift.as_dict(),
            "mode": self.mode,
            "allocation_authority": self.allocation_authority,
            "pricing_authority": self.pricing_authority,
            "settlement_authority": self.settlement_authority,
        }


def _parse_timestamp(value: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("exchange observation timestamp required")
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("exchange observation timestamp must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("exchange observation timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def _freshness_state(age: float, max_age_seconds: int) -> str:
    if age < -60:
        return "future"
    if age > max_age_seconds:
        return "stale"
    return "fresh"


def review_exchange_drift(
    *,
    baseline: ExchangeSnapshot,
    current: ExchangeSnapshot,
    reconciliation: ExchangeReconciliation,
    now: datetime,
    max_current_age_seconds: int = 21600,
    max_baseline_age_seconds: int = 604800,
) -> ExchangeEvidenceDriftReview:
    if now.tzinfo is None:
        raise ValueError("now must include timezone")
    if max_current_age_seconds <= 0 or max_baseline_age_seconds <= 0:
        raise ValueError("freshness age limits must be positive")
    if baseline.niche != current.niche or baseline.metro != current.metro:
        raise ValueError("exchange drift requires matching market identity")
    if (
        reconciliation.niche != current.niche
        or reconciliation.metro != current.metro
    ):
        raise ValueError("exchange reconciliation market identity mismatch")

    current_time = _parse_timestamp(current.observed_at)
    baseline_time = _parse_timestamp(baseline.observed_at)
    clock = now.astimezone(timezone.utc)
    current_age = (clock - current_time).total_seconds()
    baseline_age = (clock - baseline_time).total_seconds()
    current_state = _freshness_state(
        current_age, max_current_age_seconds
    )
    baseline_state = _freshness_state(
        baseline_age, max_baseline_age_seconds
    )
    freshness = ExchangeFreshness(
        current_age_seconds=round(current_age, 3),
        baseline_age_seconds=round(baseline_age, 3),
        current_freshness=current_state,
        baseline_freshness=baseline_state,
    )


    blockers: list[str] = []
    if current_state != "fresh":
        blockers.append(f"current_snapshot_{current_state}")
    if baseline_state != "fresh":
        blockers.append(f"baseline_snapshot_{baseline_state}")
    if baseline_time >= current_time:
        blockers.append("baseline_not_older_than_current")
    if not reconciliation.review_ready:
        blockers.append("current_snapshot_not_reconciled")
        blockers.extend(
            f"reconciliation_{item}"
            for item in reconciliation.blockers
        )

    ratio_delta = None
    if (
        baseline.supply_demand_ratio is not None
        and current.supply_demand_ratio is not None
    ):
        ratio_delta = round(
            current.supply_demand_ratio - baseline.supply_demand_ratio,
            4,
        )

    floor_delta = None
    if (
        baseline.observed_price_floor_cents is not None
        and current.observed_price_floor_cents is not None
    ):
        floor_delta = (
            current.observed_price_floor_cents
            - baseline.observed_price_floor_cents
        )

    ceiling_delta = None
    if (
        baseline.observed_price_ceiling_cents is not None
        and current.observed_price_ceiling_cents is not None
    ):
        ceiling_delta = (
            current.observed_price_ceiling_cents
            - baseline.observed_price_ceiling_cents
        )


    price_set_changed = None
    if (
        baseline.verified_price_per_lead_cents
        and current.verified_price_per_lead_cents
    ):
        price_set_changed = (
            tuple(sorted(baseline.verified_price_per_lead_cents))
            != tuple(sorted(current.verified_price_per_lead_cents))
        )

    ordered = tuple(sorted(set(blockers)))
    drift = ExchangeMarketDrift(
        niche=current.niche,
        metro=current.metro,
        inventory_delta=(
            current.qualified_inventory_count
            - baseline.qualified_inventory_count
        ),
        buyer_capacity_delta=(
            current.active_buyer_capacity
            - baseline.active_buyer_capacity
        ),
        supply_demand_ratio_delta=ratio_delta,
        price_floor_delta_cents=floor_delta,
        price_ceiling_delta_cents=ceiling_delta,
        verified_price_set_changed=price_set_changed,
        drift_available=not ordered,
        blockers=ordered,
    )
    return ExchangeEvidenceDriftReview(
        freshness=freshness,
        reconciliation=reconciliation,
        drift=drift,
    )
