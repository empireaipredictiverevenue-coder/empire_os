"""Phase 13 canonical source reconciliation for Revenue Exchange."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.revenue_exchange import ExchangeSnapshot


@dataclass(frozen=True)
class ExchangeEvidenceSnapshot:
    inventory_count: int | None
    buyer_capacity: int | None
    verified_prices_cents: tuple[int, ...] | None
    evidence_refs: tuple[str, ...]

    def validate(self) -> None:
        if self.inventory_count is not None and self.inventory_count < 0:
            raise ValueError("inventory_count must be nonnegative")
        if self.buyer_capacity is not None and self.buyer_capacity < 0:
            raise ValueError("buyer_capacity must be nonnegative")
        if self.verified_prices_cents is not None:
            if any(value <= 0 for value in self.verified_prices_cents):
                raise ValueError("verified prices must be positive")
        if not self.evidence_refs:
            raise ValueError("exchange reconciliation requires evidence")


@dataclass(frozen=True)
class ExchangeReconciliation:
    niche: str
    metro: str
    review_ready: bool
    inventory_reconciled: bool
    capacity_reconciled: bool
    pricing_reconciled: bool
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    allocation_authority: str = "none"
    pricing_authority: str = "none"
    settlement_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def reconcile_exchange_snapshot(
    snapshot: ExchangeSnapshot,
    evidence: ExchangeEvidenceSnapshot,
) -> ExchangeReconciliation:
    evidence.validate()

    blockers: list[str] = []

    inventory_reconciled = (
        evidence.inventory_count is not None
        and evidence.inventory_count == snapshot.qualified_inventory_count
    )
    if evidence.inventory_count is None:
        blockers.append("inventory_evidence_missing")
    elif not inventory_reconciled:
        blockers.append("inventory_count_mismatch")

    capacity_reconciled = (
        evidence.buyer_capacity is not None
        and evidence.buyer_capacity == snapshot.active_buyer_capacity
    )
    if evidence.buyer_capacity is None:
        blockers.append("buyer_capacity_evidence_missing")
    elif not capacity_reconciled:
        blockers.append("buyer_capacity_mismatch")

    observed_prices = tuple(sorted(snapshot.verified_price_per_lead_cents))
    evidence_prices = (
        tuple(sorted(evidence.verified_prices_cents))
        if evidence.verified_prices_cents is not None
        else None
    )
    pricing_reconciled = (
        evidence_prices is not None and evidence_prices == observed_prices
    )
    if evidence_prices is None:
        blockers.append("verified_price_evidence_missing")
    elif not pricing_reconciled:
        blockers.append("verified_price_mismatch")

    ordered = tuple(sorted(set(blockers)))
    return ExchangeReconciliation(
        niche=snapshot.niche,
        metro=snapshot.metro,
        review_ready=not ordered,
        inventory_reconciled=inventory_reconciled,
        capacity_reconciled=capacity_reconciled,
        pricing_reconciled=pricing_reconciled,
        blockers=ordered,
        evidence_refs=tuple(evidence.evidence_refs),
    )
