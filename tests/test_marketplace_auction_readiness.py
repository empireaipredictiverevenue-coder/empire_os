from datetime import datetime, timezone

from empire_os.marketplace_auction_readiness import (
    build_marketplace_auction_readiness,
)
from empire_os.opportunity_auction import OpportunityAuctionBid
from empire_os.revenue_exchange import ExchangeSnapshot
from empire_os.revenue_exchange_reconciliation import (
    ExchangeEvidenceSnapshot,
    reconcile_exchange_snapshot,
)

NOW = datetime(2026, 10, 2, 9, 0, tzinfo=timezone.utc)


def snapshot(**overrides):
    values = {
        "niche": "roofing",
        "metro": "London",
        "qualified_inventory_count": 12,
        "active_buyer_capacity": 8,
        "verified_price_per_lead_cents": (12000, 15000),
        "observed_at": "2026-10-02T08:30:00+00:00",
        "source": "canonical_market_snapshot",
    }
    values.update(overrides)
    return ExchangeSnapshot(**values)


def reconciliation(item):
    return reconcile_exchange_snapshot(
        item,
        ExchangeEvidenceSnapshot(
            inventory_count=item.qualified_inventory_count,
            buyer_capacity=item.active_buyer_capacity,
            verified_prices_cents=item.verified_price_per_lead_cents,
            evidence_refs=("exchange:canonical:1",),
        ),
    )


def bid(**overrides):
    values = {
        "bid_id": "bid-1",
        "opportunity_id": "opp-1",
        "buyer_id": "buyer-1",
        "bid_amount_cents": 15000,
        "currency": "USD",
        "bid_verified": True,
        "bid_evidence_ref": "bid:1",
        "buyer_capacity_remaining": 2,
        "capacity_evidence_ref": "capacity:buyer-1",
        "territory_eligible": True,
        "territory_evidence_ref": "territory:buyer-1",
        "exclusivity_clear": True,
        "exclusivity_evidence_ref": "exclusive:buyer-1",
        "observed_at": "2026-10-02T08:00:00+00:00",
        "expires_at": "2026-10-03T00:00:00+00:00",
    }
    values.update(overrides)
    return OpportunityAuctionBid(**values)


def build(item=None, bids=None, **overrides):
    item = item or snapshot()
    values = {
        "snapshot": item,
        "reconciliation": reconciliation(item),
        "bids": tuple(bids if bids is not None else (bid(),)),
        "opportunity_id": "opp-1",
        "currency": "USD",
        "reserve_floor_cents": 10000,
        "reserve_evidence_ref": "reserve:opp-1",
        "now": NOW,
        "max_age_seconds": 7200,
    }
    values.update(overrides)
    return build_marketplace_auction_readiness(**values)


def test_ready_market_and_auction_compose_without_execution_authority():
    result = build()

    assert result.auction_status == "AVAILABLE"
    assert result.recommended_bid["buyer_id"] == "buyer-1"
    assert result.ready_for_operator_allocation_review is True
    assert result.blockers == ()
    assert result.currency == "USD"
    assert result.reserve_floor_cents == 10000
    assert "exchange:canonical:1" in result.evidence_refs
    assert "reserve:opp-1" in result.evidence_refs
    assert result.mode == "OBSERVE"
    assert result.execution_authority == "none"
    assert result.allocation_authority == "none"
    assert result.pricing_authority == "none"
    assert result.settlement_authority == "none"
    assert result.binding_terms_authority == "none"
    assert result.allocation_execution is False
    assert result.payment_action is False
    assert result.revenue_recognition is False


def test_reserve_is_explicit_and_never_inferred_from_inventory():
    result = build(reserve_floor_cents=20000)

    assert result.qualified_inventory_count == 12
    assert result.reserve_floor_cents == 20000
    assert result.auction_status == "UNAVAILABLE"
    assert result.blocked_bids[0]["reasons"] == ("below_reserve",)
    assert "auction_not_ready" in result.blockers


def test_currency_is_explicit_and_not_metro():
    result = build()

    assert result.metro == "London"
    assert result.currency == "USD"
    assert result.recommended_bid["currency"] == "USD"


def test_zero_exchange_capacity_blocks_allocation_even_if_bid_is_eligible():
    item = snapshot(active_buyer_capacity=0)
    result = build(item=item)

    assert result.auction_status == "AVAILABLE"
    assert result.ready_for_operator_allocation_review is False
    assert "verified_buyer_capacity_not_available" in result.blockers


def test_opportunity_mismatch_fails_closed_in_auction_preview():
    result = build(bids=(bid(opportunity_id="different-opp"),))

    assert result.auction_status == "UNAVAILABLE"
    assert result.recommended_bid is None
    assert result.blocked_bids[0]["reasons"] == ("opportunity_mismatch",)
    assert "auction_not_ready" in result.blockers


def test_required_auction_identity_and_reserve_evidence_fail_closed():
    for field, value in (
        ("opportunity_id", ""),
        ("currency", ""),
        ("reserve_evidence_ref", ""),
    ):
        try:
            build(**{field: value})
        except ValueError as exc:
            assert field in str(exc)
        else:
            raise AssertionError(f"{field} should be required")
