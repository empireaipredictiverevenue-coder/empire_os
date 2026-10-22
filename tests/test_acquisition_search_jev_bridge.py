import pytest
from empire_os.acquisition_search_jev_bridge import summarize_search_jev_acquisition

def sample():
    return {"incoming":[{"status":"INTERNAL_RESEARCH_REVIEW_ONLY",
       "source":"market_sweeps_revenue_gps","product_key":"growth_audit",
       "outbound_authorized":False,"buyer_identity_verified":False}]}

def test_source_product_observation_only():
    r=summarize_search_jev_acquisition(sample())
    assert r["product_counts"]["growth_audit"]==1
    assert r["source_counts"]["market_sweeps_revenue_gps"]==1
    assert not r["model_training_authorized"]

def test_untrusted_promoted_record_rejected():
    x=sample();x["incoming"][0]["buyer_identity_verified"]=True
    with pytest.raises(ValueError):summarize_search_jev_acquisition(x)

def test_missing_contract_rejected():
    with pytest.raises(ValueError):summarize_search_jev_acquisition({})
