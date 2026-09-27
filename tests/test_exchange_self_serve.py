import pytest

import empire_os.exchange_self_serve as exchange


def test_public_exchange_catalog_is_non_binding():
    result = exchange.exchange_tier_catalog()

    assert result["count"] == 4
    assert result["monthly_membership"] is True
    assert result["pricing_binding"] is False
    assert result["actual_revenue"] is False


def test_exchange_interest_records_buyer_stated_demand():
    calls = []

    def request(method, path, payload=None, **kwargs):
        calls.append((method, path, payload))
        assert path.endswith("/propose_buyer_scout_candidate")
        assert payload["p_direct_buyer_score"] == 0
        assert payload["p_explicit_direct_buyer_evidence"] is False
        assert payload["p_target_product_codes"] == ["exchange_seat_growth"]
        assert payload["p_target_corridor_keys"] == [
            "requested:roofing:greater-manchester"
        ]
        evidence = payload["p_query_evidence"][0]
        assert evidence["daily_capacity"] == 12
        assert evidence["capacity_verified"] is False
        assert evidence["commercial_terms_verified"] is False
        return {
            "decision": "candidate_recorded",
            "candidate_id": "candidate-1",
            "actual_revenue": False,
        }

    result = exchange.record_exchange_interest(
        tier_code="exchange_seat_growth",
        business_name="Example Roofing Ltd",
        email="buyer@example.com",
        domain="example.com",
        niche="Roofing",
        territory="Greater Manchester",
        daily_capacity=12,
        delivery_preference="webhook",
        request=request,
    )

    assert result["decision"] == "interest_recorded"
    assert result["seat_activated"] is False
    assert result["pricing_binding"] is False
    assert result["actual_revenue"] is False
    assert len(calls) == 1


def test_starter_cannot_request_exclusivity():
    with pytest.raises(
        exchange.ExchangeInterestError,
        match="not eligible for exclusivity",
    ):
        exchange.record_exchange_interest(
            tier_code="exchange_seat_starter",
            business_name="Example Roofing Ltd",
            email="buyer@example.com",
            domain="example.com",
            niche="Roofing",
            territory="Manchester",
            daily_capacity=4,
            delivery_preference="email",
            exclusivity_interest=True,
            request=lambda *args, **kwargs: None,
        )
