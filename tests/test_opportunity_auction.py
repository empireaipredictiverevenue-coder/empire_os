from datetime import datetime, timezone

from empire_os.opportunity_auction import (
    OpportunityAuctionBid,
    preview_opportunity_auction,
)


NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def bid(
    bid_id,
    buyer,
    amount,
    *,
    capacity=2,
    verified=True,
    observed_at="2026-10-01T10:00:00+00:00",
    expires_at="2026-10-02T00:00:00+00:00",
):
    return OpportunityAuctionBid(
        bid_id=bid_id,
        opportunity_id="opp-1",
        buyer_id=buyer,
        bid_amount_cents=amount,
        currency="USD",
        bid_verified=verified,
        bid_evidence_ref=f"bid-evidence:{bid_id}",
        buyer_capacity_remaining=capacity,
        capacity_evidence_ref=f"capacity:{buyer}",
        territory_eligible=True,
        territory_evidence_ref=f"territory:{buyer}",
        exclusivity_clear=True,
        exclusivity_evidence_ref=f"exclusive:{buyer}",
        observed_at=observed_at,
        expires_at=expires_at,
    )


def preview(rows, **overrides):
    values = {
        "opportunity_id": "opp-1",
        "currency": "USD",
        "reserve_floor_cents": 10000,
        "reserve_evidence_ref": "reserve:opp-1",
        "as_of": NOW,
    }
    values.update(overrides)
    return preview_opportunity_auction(rows, **values)


def test_highest_verified_bid_is_recommended_with_alternates():
    result = preview([
        bid("b1", "buyer-1", 12000),
        bid("b2", "buyer-2", 15000),
        bid("b3", "buyer-3", 14000),
    ])

    assert result.status == "AVAILABLE"
    assert result.recommended_bid["buyer_id"] == "buyer-2"
    assert [row["buyer_id"] for row in result.eligible_alternates] == [
        "buyer-3",
        "buyer-1",
    ]
    assert result.clearing_rule == "HIGHEST_VERIFIED_BID"


def test_below_reserve_is_blocked():
    result = preview([bid("b1", "buyer-1", 9000)])

    assert result.status == "UNAVAILABLE"
    assert result.blocked_bids[0]["reasons"] == ("below_reserve",)


def test_missing_capacity_blocks_even_high_bid():
    row = bid("b1", "buyer-1", 20000)
    row = OpportunityAuctionBid(
        **{
            **row.__dict__,
            "buyer_capacity_remaining": None,
            "capacity_evidence_ref": None,
        }
    )
    result = preview([row])

    assert result.status == "UNAVAILABLE"
    assert "buyer_capacity_evidence_missing" in result.blocked_bids[0]["reasons"]


def test_expired_bid_is_blocked():
    result = preview([
        bid(
            "b1",
            "buyer-1",
            20000,
            expires_at="2026-10-01T11:59:00+00:00",
        )
    ])

    assert result.status == "UNAVAILABLE"
    assert "bid_expired" in result.blocked_bids[0]["reasons"]


def test_duplicate_active_bids_from_same_buyer_fail_closed():
    result = preview([
        bid("b1", "buyer-1", 12000),
        bid("b2", "buyer-1", 15000),
    ])

    assert result.status == "UNAVAILABLE"
    assert result.blocked_bid_count == 2
    assert all(
        "duplicate_active_buyer_bid" in row["reasons"]
        for row in result.blocked_bids
    )


def test_tie_is_deterministic_by_earliest_observation():
    result = preview([
        bid(
            "later",
            "buyer-1",
            15000,
            observed_at="2026-10-01T11:00:00+00:00",
        ),
        bid(
            "earlier",
            "buyer-2",
            15000,
            observed_at="2026-10-01T10:00:00+00:00",
        ),
    ])

    assert result.recommended_bid["bid_id"] == "earlier"


def test_bid_amount_is_never_expected_value_or_execution_authority():
    result = preview([bid("b1", "buyer-1", 15000)])

    assert result.recommended_bid["bid_amount_is_expected_value"] is False
    assert result.bid_amount_is_expected_value is False
    assert result.allocation_execution is False
    assert result.binding_terms is False
    assert result.payment_action is False
    assert result.settlement_action is False
    assert result.revenue_recognition is False
    assert result.execution_authority == "none"


def test_revenue_exchange_api_exposes_observe_only_auction_preview():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from empire_os.revenue_exchange_api import create_revenue_exchange_router

    app = FastAPI()
    app.include_router(create_revenue_exchange_router())
    response = TestClient(app).post(
        "/v1/revenue-exchange/auction/preview",
        json={
            "opportunity_id": "opp-1",
            "currency": "USD",
            "reserve_floor_cents": 10000,
            "reserve_evidence_ref": "reserve:opp-1",
            "as_of": "2026-10-01T12:00:00+00:00",
            "bids": [{
                "bid_id": "b1",
                "opportunity_id": "opp-1",
                "buyer_id": "buyer-1",
                "bid_amount_cents": 15000,
                "currency": "USD",
                "bid_verified": True,
                "bid_evidence_ref": "bid:b1",
                "buyer_capacity_remaining": 2,
                "capacity_evidence_ref": "capacity:buyer-1",
                "territory_eligible": True,
                "territory_evidence_ref": "territory:buyer-1",
                "exclusivity_clear": True,
                "exclusivity_evidence_ref": "exclusive:buyer-1",
                "observed_at": "2026-10-01T10:00:00+00:00",
                "expires_at": "2026-10-02T00:00:00+00:00",
            }],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["auction"]["status"] == "AVAILABLE"
    assert body["auction"]["recommended_bid"]["buyer_id"] == "buyer-1"
    assert body["auction"]["bid_amount_is_expected_value"] is False
    assert body["auction"]["allocation_execution"] is False
    assert body["auction"]["binding_terms"] is False
    assert body["settlement_authority"] == "none"
    assert body["execution_authority"] == "none"
