"""Evidence-only Opportunity Auction preview for EmpireOS.

Ranks verified buyer-stated bids for operator review. A bid is commercial offer
evidence, never Predictive Revenue expected value or binding terms.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable


@dataclass(frozen=True)
class OpportunityAuctionBid:
    bid_id: str
    opportunity_id: str
    buyer_id: str
    bid_amount_cents: int
    currency: str
    bid_verified: bool
    bid_evidence_ref: str | None
    buyer_capacity_remaining: int | None
    capacity_evidence_ref: str | None
    territory_eligible: bool | None
    territory_evidence_ref: str | None
    exclusivity_clear: bool | None
    exclusivity_evidence_ref: str | None
    observed_at: str
    expires_at: str | None = None

    def validate(self) -> None:
        for label, value in (
            ("bid_id", self.bid_id),
            ("opportunity_id", self.opportunity_id),
            ("buyer_id", self.buyer_id),
            ("currency", self.currency),
            ("observed_at", self.observed_at),
        ):
            if not str(value or "").strip():
                raise ValueError(f"{label} required")
        if self.bid_amount_cents <= 0:
            raise ValueError("bid_amount_cents must be positive")
        if (
            self.buyer_capacity_remaining is not None
            and self.buyer_capacity_remaining < 0
        ):
            raise ValueError(
                "buyer_capacity_remaining must be nonnegative"
            )
        _parse_time(self.observed_at, "observed_at")
        if self.expires_at:
            _parse_time(self.expires_at, "expires_at")


@dataclass(frozen=True)
class OpportunityAuctionPreview:
    opportunity_id: str
    currency: str
    reserve_floor_cents: int
    clearing_rule: str
    status: str
    recommended_bid: dict[str, Any] | None
    eligible_alternates: tuple[dict[str, Any], ...]
    blocked_bids: tuple[dict[str, Any], ...]
    eligible_bid_count: int
    blocked_bid_count: int
    recommendation_only: bool = True
    bid_amount_is_expected_value: bool = False
    allocation_execution: bool = False
    binding_terms: bool = False
    pricing_mutation: bool = False
    payment_action: bool = False
    settlement_action: bool = False
    revenue_recognition: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_time(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def preview_opportunity_auction(
    bids: Iterable[OpportunityAuctionBid],
    *,
    opportunity_id: str,
    currency: str,
    reserve_floor_cents: int,
    reserve_evidence_ref: str | None,
    as_of: datetime | None = None,
) -> OpportunityAuctionPreview:
    opp = str(opportunity_id or "").strip()
    curr = str(currency or "").strip().upper()
    reserve_ref = str(reserve_evidence_ref or "").strip()
    if not opp:
        raise ValueError("opportunity_id required")
    if not curr:
        raise ValueError("currency required")
    if reserve_floor_cents < 0:
        raise ValueError("reserve_floor_cents must be nonnegative")
    if not reserve_ref:
        raise ValueError("reserve_evidence_ref required")

    now = (as_of or datetime.now(timezone.utc)).astimezone(
        timezone.utc
    )
    rows = list(bids)
    for row in rows:
        row.validate()

    buyer_counts: dict[str, int] = {}
    for row in rows:
        if row.opportunity_id == opp:
            buyer_counts[row.buyer_id] = (
                buyer_counts.get(row.buyer_id, 0) + 1
            )

    eligible: list[OpportunityAuctionBid] = []
    blocked: list[dict[str, Any]] = []

    for row in rows:
        reasons: list[str] = []

        if row.opportunity_id != opp:
            reasons.append("opportunity_mismatch")
        if row.currency.strip().upper() != curr:
            reasons.append("currency_mismatch")
        if buyer_counts.get(row.buyer_id, 0) > 1:
            reasons.append("duplicate_active_buyer_bid")
        if row.bid_verified is not True:
            reasons.append("bid_not_verified")
        if not str(row.bid_evidence_ref or "").strip():
            reasons.append("bid_evidence_missing")
        if row.bid_amount_cents < reserve_floor_cents:
            reasons.append("below_reserve")
        if (
            row.buyer_capacity_remaining is None
            or not str(row.capacity_evidence_ref or "").strip()
        ):
            reasons.append("buyer_capacity_evidence_missing")
        elif row.buyer_capacity_remaining <= 0:
            reasons.append("buyer_capacity_unavailable")
        if (
            row.territory_eligible is not True
            or not str(row.territory_evidence_ref or "").strip()
        ):
            reasons.append("territory_not_verified_eligible")
        if (
            row.exclusivity_clear is not True
            or not str(row.exclusivity_evidence_ref or "").strip()
        ):
            reasons.append("exclusivity_not_verified_clear")

        if row.expires_at:
            if _parse_time(row.expires_at, "expires_at") <= now:
                reasons.append("bid_expired")

        if reasons:
            blocked.append({
                "bid_id": row.bid_id,
                "buyer_id": row.buyer_id,
                "bid_amount_cents": row.bid_amount_cents,
                "reasons": tuple(sorted(set(reasons))),
            })
        else:
            eligible.append(row)

    eligible.sort(
        key=lambda row: (
            -row.bid_amount_cents,
            _parse_time(row.observed_at, "observed_at"),
            row.buyer_id,
            row.bid_id,
        )
    )

    def public_bid(row: OpportunityAuctionBid) -> dict[str, Any]:
        return {
            "bid_id": row.bid_id,
            "buyer_id": row.buyer_id,
            "bid_amount_cents": row.bid_amount_cents,
            "currency": curr,
            "buyer_capacity_remaining": row.buyer_capacity_remaining,
            "bid_evidence_ref": row.bid_evidence_ref,
            "capacity_evidence_ref": row.capacity_evidence_ref,
            "territory_evidence_ref": row.territory_evidence_ref,
            "exclusivity_evidence_ref": row.exclusivity_evidence_ref,
            "observed_at": row.observed_at,
            "expires_at": row.expires_at,
            "bid_amount_is_expected_value": False,
        }

    recommended = public_bid(eligible[0]) if eligible else None
    alternates = tuple(public_bid(row) for row in eligible[1:])

    return OpportunityAuctionPreview(
        opportunity_id=opp,
        currency=curr,
        reserve_floor_cents=reserve_floor_cents,
        clearing_rule="HIGHEST_VERIFIED_BID",
        status="AVAILABLE" if recommended else "UNAVAILABLE",
        recommended_bid=recommended,
        eligible_alternates=alternates,
        blocked_bids=tuple(blocked),
        eligible_bid_count=len(eligible),
        blocked_bid_count=len(blocked),
    )
