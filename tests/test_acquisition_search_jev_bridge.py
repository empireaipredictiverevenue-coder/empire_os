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

def test_real_gtm_observer_contract():
    from datetime import datetime, timezone
    from empire_os.gtm_integration_observer import build_gtm_integration_observation
    now = datetime(2026,10,23,tzinfo=timezone.utc)
    radar = {"mode":"OBSERVE", "source_status":{"market_gps":{"available":True}},
             "candidates":[{"opportunity_key":"market-1",
                 "source":"market_sweeps_revenue_gps", "offer_key":"roof_quote",
                 "evidence_refs":["source:1"],"execution_authority":"none"}]}
    observed = build_gtm_integration_observation(
        radar, {}, now=now, radar_source_fresh=True, commercial_loop_fresh=False)
    result = summarize_search_jev_acquisition(observed)
    assert result["research_handoff_count"] == 1
    assert result["research_queue"][0]["product_code"] == "roof_quote"
    assert result["research_queue"][0]["qualification_status"] == "RESEARCH_ONLY"
    assert not result["outbound_authorized"]

def test_live_shape_rejects_missing_authority():
    from datetime import datetime, timezone
    from empire_os.gtm_integration_observer import build_gtm_integration_observation
    observed = build_gtm_integration_observation(
        {"mode":"OBSERVE","source_status":{},"candidates":[]}, {},
        now=datetime(2026,10,23,tzinfo=timezone.utc),
        radar_source_fresh=False, commercial_loop_fresh=False)
    observed["authority"]="outbound"
    with pytest.raises(ValueError):
        summarize_search_jev_acquisition(observed)
