from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.revenue_exchange import ExchangeSnapshot
from empire_os.revenue_exchange_allocation_proposal import (
    ExchangeAllocationProposalEvidence,
    review_exchange_allocation_proposal,
)
from empire_os.revenue_exchange_allocation_readiness import ExchangeAllocationReadiness
from empire_os.revenue_exchange_api import create_revenue_exchange_router


def snapshot():
    return ExchangeSnapshot(
        niche="roofing",
        metro="Austin, TX",
        qualified_inventory_count=12,
        active_buyer_capacity=8,
        verified_price_per_lead_cents=(12000, 15000),
        observed_at="2026-09-20T15:00:00+00:00",
        source="canonical",
    )


def readiness(**overrides):
    values = {
        "niche": "roofing",
        "metro": "Austin, TX",
        "ready_for_operator_allocation_review": True,
        "current_age_seconds": 3600.0,
        "blockers": (),
        "evidence_refs": ("exchange:reconciliation:1",),
    }
    values.update(overrides)
    return ExchangeAllocationReadiness(**values)


def evidence(**overrides):
    values = {
        "inventory_id": "prospect-1",
        "buyer_id": "buyer-1",
        "niche": "roofing",
        "metro": "Austin, TX",
        "inventory_qualified": True,
        "inventory_evidence_ref": "qualification:1",
        "buyer_capacity_remaining": 3,
        "buyer_capacity_evidence_ref": "buyer-capacity:1",
        "proposed_price_cents": 12000,
        "verified_price_evidence_ref": "commercial-terms:1",
        "territory_eligible": True,
        "territory_evidence_ref": "territory:1",
        "exclusivity_clear": True,
        "exclusivity_evidence_ref": "exclusivity:1",
    }
    values.update(overrides)
    return ExchangeAllocationProposalEvidence(**values)


def test_complete_pairing_is_operator_match_review_ready_only():
    review = review_exchange_allocation_proposal(
        snapshot=snapshot(), readiness=readiness(), evidence=evidence()
    )
    assert review.ready_for_operator_match_review is True
    assert review.blockers == ()
    assert review.allocation_authority == "none"
    assert review.pricing_authority == "none"
    assert review.settlement_authority == "none"
    assert review.exclusivity_authority == "none"
    assert review.funds_movement is False


def test_unverified_price_cannot_be_proposed():
    review = review_exchange_allocation_proposal(
        snapshot=snapshot(),
        readiness=readiness(),
        evidence=evidence(proposed_price_cents=13000),
    )
    assert review.ready_for_operator_match_review is False
    assert "proposed_price_not_in_verified_market_set" in review.blockers


def test_zero_buyer_capacity_blocks_pairing():
    review = review_exchange_allocation_proposal(
        snapshot=snapshot(),
        readiness=readiness(),
        evidence=evidence(buyer_capacity_remaining=0),
    )
    assert review.ready_for_operator_match_review is False
    assert "buyer_capacity_not_available" in review.blockers


def test_territory_or_exclusivity_uncertainty_blocks_pairing():
    review = review_exchange_allocation_proposal(
        snapshot=snapshot(),
        readiness=readiness(),
        evidence=evidence(
            territory_eligible=None,
            territory_evidence_ref=None,
            exclusivity_clear=False,
        ),
    )
    assert review.ready_for_operator_match_review is False
    assert "territory_eligibility_evidence_missing" in review.blockers
    assert "exclusivity_conflict_observed" in review.blockers


def test_api_proposal_preview_never_allocates_or_settles():
    app = FastAPI()
    app.include_router(create_revenue_exchange_router())
    response = TestClient(app).post(
        "/v1/revenue-exchange/allocation/proposal/preview",
        json={
            "row": {
                "niche": "roofing",
                "metro": "Austin, TX",
                "qualified_inventory_count": 12,
                "active_buyer_capacity": 8,
                "verified_price_per_lead_cents": [12000, 15000],
                "observed_at": "2026-09-20T15:00:00+00:00",
                "source": "canonical",
            },
            "inventory_count": 12,
            "buyer_capacity": 8,
            "verified_prices_cents": [12000, 15000],
            "evidence_refs": ["exchange:reconciliation:1"],
            "now_utc": "2026-09-20T16:00:00+00:00",
            "inventory_id": "prospect-1",
            "buyer_id": "buyer-1",
            "inventory_qualified": True,
            "inventory_evidence_ref": "qualification:1",
            "buyer_capacity_remaining": 3,
            "buyer_capacity_evidence_ref": "buyer-capacity:1",
            "proposed_price_cents": 12000,
            "verified_price_evidence_ref": "commercial-terms:1",
            "territory_eligible": True,
            "territory_evidence_ref": "territory:1",
            "exclusivity_clear": True,
            "exclusivity_evidence_ref": "exclusivity:1",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["allocation_authority"] == "none"
    assert body["settlement_authority"] == "none"
    assert body["pricing_authority"] == "none"
    assert body["exclusivity_authority"] == "none"
    assert body["funds_movement"] is False
    assert body["proposal"]["ready_for_operator_match_review"] is True
