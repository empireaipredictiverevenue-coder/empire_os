"""Source-route failover never invents health, buyers or API permissions."""
from __future__ import annotations

from copy import deepcopy
import pytest

from empire_os.a2a_source_route_resilience_v1 import build_source_route_board


def inputs():
    source={
        "schema_version":"empire.a2a.first_party_source_recovery_review.v1",
        "execution_authority":"NONE",
        "new_verified_sales_leads":0,"outbound_sent":0,
        "source_state":"CACHED_FIRST_PARTY_PUBLIC_RESEARCH_WITHIN_7_DAYS",
        "market_coverage":{
            "tampa, fl":{"sector":"roofing","successful_site_reads":3,
                         "self_described_sector_and_region_matches":3},
            "little rock, ar":{"sector":"hvac","successful_site_reads":3,
                                "self_described_sector_and_region_matches":3},
            "nyc":{"sector":"general_contractor","successful_site_reads":1,
                   "self_described_sector_and_region_matches":1},
        },
        "source_records":[
            {"market":"tampa, fl","scrapling_structured_page_parsed":True},
            {"market":"tampa, fl","scrapling_structured_page_parsed":True},
            {"market":"tampa, fl","scrapling_structured_page_parsed":True},
            {"market":"little rock, ar","scrapling_structured_page_parsed":True},
            {"market":"little rock, ar","scrapling_structured_page_parsed":True},
            {"market":"little rock, ar","scrapling_structured_page_parsed":True},
            {"market":"nyc","scrapling_structured_page_parsed":True},
        ],
    }
    mining={
        "schema_version":"empire.a2a.public_business_evidence_mining.v1",
        "execution_authority":"NONE","verified_real_lead_count":0,
        "public_provider_fresh_search_status":"NO_FRESH_DOMAIN_RESULTS_PROVIDER_HEALTH_UNVERIFIED",
    }
    manus={
        "schema_version":"empire.a2a.openmanus_scoped_owner_research_plan.v1",
        "execution_authority":"NONE","jobs_prepared":3,
        "jobs_executed":0,"production_jobs_dispatched":0,
    }
    reach={
        "doctor":{"rss":{"status":"ok"},"web":{"status":"ok"},
                  "facebook":{"status":"off"},"instagram":{"status":"off"}},
        "probe_performed":False,
    }
    return source,mining,manus,reach


def test_source_routing_uses_read_receipts_not_unverified_search_health():
    v=build_source_route_board(*inputs())
    assert not v["keyless_search_restored"]
    assert v["source_routes"][0]["scrapling_structured_extractions_from_cached_reads"]==3
    assert v["source_routes"][2]["first_party_reads_verified_by_local_collector"]==1
    assert v["agent_reach_doctor"]["rss"]["doctor_reported_status"]=="ok"
    assert v["agent_reach_doctor"]["facebook"]["doctor_reported_status"]=="off"
    assert not v["agent_reach_doctor"]["rss"]["live_query_success_proven_in_this_cycle"]
    assert v["new_verified_leads"]==0
    assert not v["paid_search_provider_authorized_by_this_plan"]


def test_stale_source_is_not_recommended_as_current_city_demand():
    s,m,o,h=inputs()
    s["source_state"]="STALE_FIRST_PARTY_PUBLIC_RESEARCH_OVER_7_DAYS"
    v=build_source_route_board(s,m,o,h)
    assert all(x["first_party_reads_verified_by_local_collector"] is None
               for x in v["source_routes"])
    assert all(x["scrapling_structured_extractions_from_cached_reads"] is None
               for x in v["source_routes"])


def test_escalated_source_and_fake_manus_dispatch_are_rejected():
    s,m,o,h=inputs()
    s["new_verified_sales_leads"]=1
    with pytest.raises(ValueError,match="UNTRUSTED_FIRST_PARTY"):
        build_source_route_board(s,m,o,h)
    s,m,o,h=inputs()
    o["production_jobs_dispatched"]=3
    with pytest.raises(ValueError,match="UNTRUSTED_EXECUTOR"):
        build_source_route_board(s,m,o,h)
    s,m,o,h=inputs()
    m["verified_real_lead_count"]=5
    with pytest.raises(ValueError,match="UNTRUSTED_PUBLIC_MINING"):
        build_source_route_board(s,m,o,h)
