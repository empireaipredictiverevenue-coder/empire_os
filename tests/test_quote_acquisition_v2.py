import pytest
from empire_os.quote_acquisition_review import GATES
from empire_os.quote_acquisition_v2 import rank_quote_buyers

def candidate(key, **kw):
    return dict(buyer_ref=key, contracted=True, service_match=True,
                territory_match=True, capacity_verified=True, terms_accepted=True,
                delivery_permission=True, **kw)
def request():
    return dict.fromkeys(GATES, True)

def test_rank_verified_economics_and_no_actions():
    result = rank_quote_buyers(vertical="roofing", request=request(), candidates=[
        candidate("a", price_verified=True, accepted_lead_price="100", cost_verified=True, verified_delivery_cost="40", currency="GBP", remaining_capacity=2),
        candidate("b", price_verified=True, accepted_lead_price="120", cost_verified=True, verified_delivery_cost="20", currency="GBP", remaining_capacity=2)])
    assert [x["buyer_ref"] for x in result["ranked_candidates"]] == ["b", "a"]
    assert result["ranked_candidates"][0]["verified_unit_margin"] == "100"
    assert result["realised_revenue"] is None
    assert result["outbound_authorized"] is False

def test_no_consent_blocks_all():
    req = request(); req["contact_permission"] = False
    r = rank_quote_buyers(vertical="hvac", request=req, candidates=[candidate("a")])
    assert r["ranked_candidates"][0]["status"] == "HOLD"

def test_zero_capacity_holds():
    r = rank_quote_buyers(vertical="solar", request=request(), candidates=[
        candidate("a", remaining_capacity=0)])
    assert r["ranked_candidates"][0]["status"] == "HOLD"

def test_fabricated_prices_not_counted():
    r = rank_quote_buyers(vertical="roofing", request=request(), candidates=[
        candidate("a", accepted_lead_price="1000", verified_delivery_cost="1")])
    assert r["ranked_candidates"][0]["verified_unit_margin"] is None

def test_reject_bad_or_duplicate_buyer_references():
    with pytest.raises(ValueError):
        rank_quote_buyers(vertical="roofing", request=request(), candidates=[candidate("a"), candidate("a")])
    with pytest.raises(ValueError):
        rank_quote_buyers(vertical="roofing", request=request(), candidates=[candidate("")])
