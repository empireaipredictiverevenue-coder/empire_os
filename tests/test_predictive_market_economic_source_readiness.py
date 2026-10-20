"""Synthetic provenance/freshness and false market-demand claim regression."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from empire_os.predictive_market_economic_source_readiness import (
    review_market_economic_source_readiness,
    review_market_economic_source_readiness_runtime,
)

NOW=datetime(2026,10,20,8,0,tzinfo=timezone.utc)
AT=(NOW-timedelta(minutes=20)).isoformat()


def snapshots():
    return {
        "market_gps":{
            "schema_version":"empire.market_sweep_revenue_gps.v1",
            "mode":"OBSERVE","execution_authority":"none","generated_at":AT,
            "market_count":11,"competitive_evidence_market_count":2,
            "commercial_demand_market_count":0,
            "buyer_intent_inferred":False,"revenue_inferred":False,
            "outreach_enabled":False,
            "verified_product_economics":{
                "economics_kind":"founder_policy_scenario",
                "prediction":False,"actual_cost_observed":False,
                "actual_revenue":False,
                "pilot_price_cents":150000,
            },
            "private_data":"never_return@example.org",
        },
        "competitor_intelligence":{
            "schema_version":"empire.competitor_intelligence_feed.v1",
            "mode":"OBSERVE","execution_authority":"none","generated_at":AT,
            "canonical_company_count":14,"buyer_intent_inferred":False,
            "revenue_opportunity_inferred":False,"outreach_enabled":False,
        },
        "storm_opportunity":{
            "schema_version":"empire.storm_opportunity_snapshot.v1",
            "mode":"OBSERVE","execution_authority":"none","generated_at":AT,
            "candidate_count":0,"automatic_external_execution_allowed":False,
            "damage_inferred":False,"demand_inferred":False,
            "economics_inferred":False,
            "outreach_authority":"none","payment_authority":"none",
        },
    }


def review(s=None):
    return review_market_economic_source_readiness(
        s if s is not None else snapshots(),as_of=NOW,
    )


def test_fresh_owner_research_is_not_market_demand_or_real_storm_damage():
    x=review()
    assert x["status"]=="SOURCE_OWNER_MARKET_CONTEXT_REVIEWED"
    assert x["fresh_research_owner_count"]==3
    assert x["source_count"]==3
    assert x["sources"]["market_gps"]["observed_research_entities_or_markets"]==11
    assert x["sources"]["market_gps"]["competitor_evidence_market_count"]==2
    assert x["sources"]["market_gps"]["founder_policy_price_and_cost_are_not_actuals"] is True
    assert x["sources"]["storm_opportunity"]["observed_research_entities_or_markets"]==0
    assert x["sources"]["storm_opportunity"]["may_calibrate_market_shock"] is False
    assert x["product_market_price_authenticated"] is False
    assert x["real_storm_damage_or_demand_authenticated"] is False
    assert x["simulated_economic_twin_calibrated"] is False
    assert x["economic_playbook_production_authorized"] is False
    assert x["execution_authority"]=="none"
    assert "never_return@example.org" not in json.dumps(x)
    assert "150000" not in json.dumps(x)


def test_missing_and_stale_sources_are_separate_unknowns():
    s=snapshots()
    s["competitor_intelligence"]["generated_at"]=(NOW-timedelta(days=20)).isoformat()
    s["storm_opportunity"]=None
    x=review(s)
    assert x["fresh_research_owner_count"]==1
    assert x["sources"]["competitor_intelligence"]["status"]=="STALE_OR_FUTURE_HOLD"
    assert x["sources"]["storm_opportunity"]["status"]=="MISSING"
    assert x["sources"]["storm_opportunity"]["observed_research_entities_or_markets"] is None
    assert x["simulated_economic_twin_calibrated"] is False


@pytest.mark.parametrize("name,key,value",[
    ("market_gps","buyer_intent_inferred",True),
    ("market_gps","verified_product_economics",{"actual_revenue":True}),
    ("market_gps","market_count",True),
    ("market_gps","commercial_demand_market_count",100),
    ("competitor_intelligence","outreach_enabled",True),
    ("competitor_intelligence","canonical_company_count",False),
    ("storm_opportunity","damage_inferred",True),
    ("storm_opportunity","candidate_count","100"),
])
def test_untrusted_owner_and_commercial_claims_cannot_train_twin(name,key,value):
    s=snapshots()
    s[name][key]=value
    x=review(s)
    assert x["sources"][name]["status"]=="SOURCE_CLAIMS_HOLD"
    assert x["sources"][name]["may_calibrate_market_shock"] is False
    assert x["execution_authority"]=="none"


def test_fake_authority_and_bad_time_are_held():
    s=snapshots()
    s["market_gps"]["execution_authority"]="spend"
    assert review(s)["sources"]["market_gps"]["status"]=="SOURCE_CONTRACT_HOLD"
    s=snapshots()
    s["storm_opportunity"]["generated_at"]="2026-10-19"
    assert review(s)["sources"]["storm_opportunity"]["status"]=="SOURCE_TIME_HOLD"


def test_runtime_loads_only_three_aggregates_not_original_private_text(tmp_path):
    s=snapshots()
    paths={
        "market_gps":"runtime/market_sweeps/revenue_gps_latest.json",
        "competitor_intelligence":"runtime/competitive_intelligence/competitor_intelligence_feed_latest.json",
        "storm_opportunity":"runtime/storm_opportunity/latest.json",
    }
    for name,rel in paths.items():
        p=tmp_path/rel
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(s[name]))
    private=tmp_path/"runtime/market_sweeps/customer_raw_messages.json"
    private.write_text('{"raw":"DO_NOT_READ"}')
    x=review_market_economic_source_readiness_runtime(tmp_path,as_of=NOW)
    assert x["fresh_research_owner_count"]==3
    assert "DO_NOT_READ" not in json.dumps(x)
    (tmp_path/paths["storm_opportunity"]).unlink()
    x=review_market_economic_source_readiness_runtime(tmp_path,as_of=NOW)
    assert x["sources"]["storm_opportunity"]["status"]=="MISSING"
