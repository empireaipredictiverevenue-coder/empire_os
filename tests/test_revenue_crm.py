import pytest

from empire_os.revenue_crm import (
    normalise_revenue_crm_buyer,
    normalise_revenue_crm_prospect,
)


def test_prospect_projection_preserves_observed_commercial_state():
    record = normalise_revenue_crm_prospect({
        "prospect_id": "prospect-1",
        "business_name": "Example Ltd",
        "niche": "roofing",
        "metro": "London",
        "prospect_status": "qualified",
        "conversation_id": "conversation-1",
        "conversation_channel": "email",
        "conversation_state": "engaged",
        "closer_case_id": "case-1",
        "closer_state": "proposal_ready",
        "fulfilment_order_id": "order-1",
        "fulfilment_state": "accepted",
        "price_cents": 25000,
        "deal_probability": None,
    })
    assert record.prospect_id == "prospect-1"
    assert record.closer_state == "proposal_ready"
    assert record.price_cents == 25000
    assert record.deal_probability is None


def test_deal_probability_is_not_invented():
    record = normalise_revenue_crm_prospect({
        "prospect_id": "prospect-1",
    })
    assert record.deal_probability is None


def test_invalid_probability_is_rejected():
    with pytest.raises(ValueError, match="between 0 and 1"):
        normalise_revenue_crm_prospect({
            "prospect_id": "prospect-1",
            "deal_probability": 1.2,
        })
def test_buyer_projection_uses_real_capacity_math():
    buyer = normalise_revenue_crm_buyer({
        "id": "buyer-1",
        "buyer_name": "Buyer One",
        "niche": "roofing",
        "metro": "London",
        "commercial_activation_state": "activated",
        "daily_cap": 10,
        "calls_today": 4,
    })
    assert buyer.buyer_id == "buyer-1"
    assert buyer.commercial_activation_state == "activated"
    assert buyer.available_capacity == 6


def test_buyer_capacity_never_goes_negative():
    buyer = normalise_revenue_crm_buyer({
        "buyer_id": "buyer-1",
        "daily_cap": 5,
        "calls_today": 9,
    })
    assert buyer.available_capacity == 0


def test_missing_buyer_id_fails_closed():
    with pytest.raises(ValueError, match="canonical buyer_id"):
        normalise_revenue_crm_buyer({})
