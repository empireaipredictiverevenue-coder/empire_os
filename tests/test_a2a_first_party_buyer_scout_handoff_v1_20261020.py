"""Buyer Scout evidence packets must not self-promote a company's own website."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import pytest

from empire_os.a2a_first_party_buyer_scout_handoff_v1 import (
    prepare_verified_scope_buyer_scout_handoff,
    make_first_party_owner_handoff_hold,
)
from empire_os.a2a_first_party_recovery_readback_v1 import review_first_party_research
from empire_os.a2a_owner_research_protocol_v1 import make_owner_pickup_packets
from empire_os.a2a_target_owner_handoff_v1 import make_owner_research_handoffs
from empire_os.a2a_b2b_evidence_mining_v1 import mine_targeted_business_evidence
from tests.test_a2a_b2b_evidence_mining_v1_20261020 import fixture_data, NOW

def sample():
    targets, pickup, seeds, scout, permit = fixture_data()
    mining=mine_targeted_business_evidence(targets,pickup,seeds,scout,permit,now=NOW)
    sites={
        "schema_version":"empire.a2a.first_party_source_recovery_review.v1",
        "mode":"OBSERVE", "execution_authority":"NONE",
        "new_verified_sales_leads":0,"outbound_sent":0,
        "commercial_buying_intent_verified":False,
        "buyer_budget_verified":False,
        "source_records":[
            {"source_url":"https://tampa-roof.example/","market":"tampa, fl","sector":"roofing",
             "read_status":"HTTP_200","source_sha256_if_http_200":"a"*64,
             "self_description_matches_trade_and_region":True,
             "buyer_or_lead_verified":False,"contact_allowed":False},
            {"source_url":"https://little-rock-hvac.example/","market":"little rock, ar","sector":"hvac",
             "read_status":"ROBOTS_POLICY_HOLD","source_sha256_if_http_200":None,
             "self_description_matches_trade_and_region":False,
             "buyer_or_lead_verified":False,"contact_allowed":False},
        ],
    }
    return sites,pickup,mining

def test_valid_first_party_website_is_only_buyer_scout_research():
    report=prepare_verified_scope_buyer_scout_handoff(*sample())
    assert report["first_party_sites_inspected"]==2
    assert report["research_review_candidates_with_matching_self_descriptions"]==1
    assert report["scoped_review_packet_count"]==2
    assert report["verified_buyers"]==0
    assert report["canonical_buyer_records_created"]==0
    assert report["buyer_scout_owner_tasks_dispatched"]==0
    assert not report["buyer_scout_owner_acceptance_received"]
    record=report["scoped_review_packets"][0]
    assert record["ready_for_buyer_scout_owner_research_review"]
    assert record["source_read_status"]=="HTTP_200"
    assert record["public_company_domain"]=="tampa-roof.example"
    assert len(record["buyer_scout_ticket_sha256"])==64
    assert not record["lead_created"]
    assert not record["contact_authorized"]
    assert record["requires_canonical_duplicate_and_suppression_review"]


def test_source_denial_does_not_create_reviewable_buyer():
    report=prepare_verified_scope_buyer_scout_handoff(*sample())
    restricted=report["scoped_review_packets"][1]
    assert restricted["source_read_status"]=="ROBOTS_POLICY_HOLD"
    assert restricted["observed_source_sha256"] is None
    assert not restricted["ready_for_buyer_scout_owner_research_review"]


def test_outbound_status_or_false_buyer_promotion_rejected():
    source=list(sample())
    source[0]["source_records"][0]["buyer_or_lead_verified"]=True
    with pytest.raises(ValueError,match="SITE_SELF_PROMOTED"):
        prepare_verified_scope_buyer_scout_handoff(*source)
    source=list(sample())
    source[0]["commercial_buying_intent_verified"]=True
    with pytest.raises(ValueError,match="UNTRUSTED_FIRST_PARTY"):
        prepare_verified_scope_buyer_scout_handoff(*source)


def test_unknown_market_and_invalid_hash_are_rejected():
    s=list(sample())
    s[0]["source_records"][0]["market"]="newly invented region"
    with pytest.raises(ValueError,match="SITE_SCOPE_NOT_OWNED"):
        prepare_verified_scope_buyer_scout_handoff(*s)
    s=list(sample())
    s[0]["source_records"][0]["source_sha256_if_http_200"]="bad"
    with pytest.raises(ValueError,match="SOURCE_EVIDENCE_HASH"):
        prepare_verified_scope_buyer_scout_handoff(*s)


def test_duplicate_site_cannot_be_counted_twice():
    s=list(sample())
    s[0]["source_records"].append(deepcopy(s[0]["source_records"][0]))
    with pytest.raises(ValueError,match="DUPLICATE_FIRST_PARTY_SOURCE"):
        prepare_verified_scope_buyer_scout_handoff(*s)


def test_owner_source_missing_is_unknown_not_fake_zero_buyers():
    r=make_first_party_owner_handoff_hold("BUYER_OWNER_SOURCE_UNAVAILABLE")
    assert r["first_party_sites_inspected"] is None
    assert r["research_review_candidates_with_matching_self_descriptions"] is None
    assert r["buyer_scout_owner_tasks_dispatched"]==0
    assert r["verified_buyers"]==0
    with pytest.raises(ValueError):
        make_first_party_owner_handoff_hold("READY_TO_SELL")


def test_repeat_produces_identical_idempotent_packets_without_dispatch():
    site,pickup,mining=sample()
    a=prepare_verified_scope_buyer_scout_handoff(site,pickup,mining)
    b=prepare_verified_scope_buyer_scout_handoff(site,pickup,mining)
    assert [p["record_id"] for p in a["scoped_review_packets"]]==[
        p["record_id"] for p in b["scoped_review_packets"]]
    assert a["messages_sent"]==0 and not a["ads_launched"]
