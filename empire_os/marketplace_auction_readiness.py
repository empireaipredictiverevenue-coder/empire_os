"""Read-only Marketplace / Opportunity Auction readiness composition.

Composes existing Revenue Exchange allocation readiness with the existing
Opportunity Auction preview. This module owns no allocation, pricing, terms,
payment, settlement, outbound or revenue-recognition authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Iterable

from empire_os.opportunity_auction import (
    OpportunityAuctionBid,
    preview_opportunity_auction,
)
from empire_os.revenue_exchange import ExchangeSnapshot
from empire_os.revenue_exchange_allocation_readiness import (
    assess_exchange_allocation_readiness,
)
from empire_os.revenue_exchange_reconciliation import ExchangeReconciliation


@dataclass(frozen=True)
class MarketplaceAuctionReadiness:
    opportunity_id: str
    currency: str
    reserve_floor_cents: int
    niche: str
    metro: str
    qualified_inventory_count: int
    active_buyer_capacity: int
    verified_price_per_lead_cents: tuple[int, ...]
    auction_status: str
    recommended_bid: dict[str, Any] | None
    eligible_alternates: tuple[dict[str, Any], ...]
    blocked_bids: tuple[dict[str, Any], ...]
    ready_for_operator_allocation_review: bool
    allocation_blockers: tuple[str, ...]
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    current_age_seconds: float
    mode: str = "OBSERVE"
    recommendation_only: bool = True
    bid_amount_is_expected_value: bool = False
    execution_authority: str = "none"
    allocation_authority: str = "none"
    pricing_authority: str = "none"
    settlement_authority: str = "none"
    binding_terms_authority: str = "none"
    allocation_execution: bool = False
    pricing_mutation: bool = False
    payment_action: bool = False
    settlement_action: bool = False
    revenue_recognition: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clean_required(value: str, field: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field} required")
    return clean


def _evidence_refs(
    *,
    reconciliation: ExchangeReconciliation,
    reserve_evidence_ref: str,
    bids: Iterable[OpportunityAuctionBid],
) -> tuple[str, ...]:
    refs: list[str] = list(reconciliation.evidence_refs)
    refs.append(reserve_evidence_ref)
    for bid in bids:
        for value in (
            bid.bid_evidence_ref,
            bid.capacity_evidence_ref,
            bid.territory_evidence_ref,
            bid.exclusivity_evidence_ref,
        ):
            clean = str(value or "").strip()
            if clean:
                refs.append(clean)
    return tuple(dict.fromkeys(refs))


def build_marketplace_auction_readiness(
    *,
    snapshot: ExchangeSnapshot,
    reconciliation: ExchangeReconciliation,
    bids: Iterable[OpportunityAuctionBid],
    opportunity_id: str,
    currency: str,
    reserve_floor_cents: int,
    reserve_evidence_ref: str,
    now: datetime,
    max_age_seconds: int = 21600,
) -> MarketplaceAuctionReadiness:
    """Compose evidence-only marketplace and auction readiness.

    Auction identity, currency and reserve evidence are explicit inputs. They
    are never inferred from market niche, metro, inventory or observed prices.
    """
    opp = _clean_required(opportunity_id, "opportunity_id")
    curr = _clean_required(currency, "currency").upper()
    reserve_ref = _clean_required(
        reserve_evidence_ref,
        "reserve_evidence_ref",
    )
    if reserve_floor_cents < 0:
        raise ValueError("reserve_floor_cents must be nonnegative")

    rows = tuple(bids)
    allocation = assess_exchange_allocation_readiness(
        snapshot=snapshot,
        reconciliation=reconciliation,
        now=now,
        max_age_seconds=max_age_seconds,
    )
    auction = preview_opportunity_auction(
        rows,
        opportunity_id=opp,
        currency=curr,
        reserve_floor_cents=reserve_floor_cents,
        reserve_evidence_ref=reserve_ref,
        as_of=now,
    )

    blockers = list(allocation.blockers)
    if auction.status != "AVAILABLE":
        blockers.append("auction_not_ready")

    return MarketplaceAuctionReadiness(
        opportunity_id=opp,
        currency=curr,
        reserve_floor_cents=reserve_floor_cents,
        niche=snapshot.niche,
        metro=snapshot.metro,
        qualified_inventory_count=snapshot.qualified_inventory_count,
        active_buyer_capacity=snapshot.active_buyer_capacity,
        verified_price_per_lead_cents=tuple(
            snapshot.verified_price_per_lead_cents
        ),
        auction_status=auction.status,
        recommended_bid=auction.recommended_bid,
        eligible_alternates=auction.eligible_alternates,
        blocked_bids=auction.blocked_bids,
        ready_for_operator_allocation_review=(
            allocation.ready_for_operator_allocation_review
        ),
        allocation_blockers=allocation.blockers,
        blockers=tuple(sorted(set(blockers))),
        evidence_refs=_evidence_refs(
            reconciliation=reconciliation,
            reserve_evidence_ref=reserve_ref,
            bids=rows,
        ),
        current_age_seconds=allocation.current_age_seconds,
    )
