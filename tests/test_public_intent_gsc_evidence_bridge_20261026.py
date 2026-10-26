"""Regression tests for the existing first-party GSC query-page reader."""
from datetime import date
import copy
import json

import pytest

from empire_os.public_intent_offer_method_bridge import (
    IntentOfferSpec, prepare_public_intent_offer_review,
)
from empire_os.public_intent_gsc_evidence_bridge import (
    KeywordGscEvidenceError, review_gsc_keyword_ideas, read_original_loopback_gsc,
    MAX_ROWS,
)

START=date(2026,10,4)
END=date(2026,10,16)
TODAY=date(2026,10,26)


def research(seed="commercial roof repair"):
    return prepare_public_intent_offer_review(IntentOfferSpec(
        market_key="roofing-market",seed_keyword=seed,icp_key="roofing-operator",
        buyer_problem="Need repair decision before contracting",
    ))


def packet(keyword="commercial roof repair cost", page="https://empire-ai.co.uk/industries/roofing"):
    return {
        "available":True,"source":"google_search_console",
        "site_url":"sc-domain:empire-ai.co.uk",
        "count":1,"limit":MAX_ROWS,
        "items":[{"keys":[keyword,page],"clicks":1,"impressions":10,
                  "ctr":0.1,"position":11.5}],
    }


def review(data=None):
    return review_gsc_keyword_ideas(research(),data or packet(),
                                   start=START,end=END,today=TODAY)


def test_exact_first_party_query_page_is_observation_not_global_volume():
    r=review()
    assert r["owner"]=="empire_os.search_intelligence.search_console"
    assert r["gsc_query_page_rows"]==1
    assert r["exactly_observed_candidate_queries"]==1
    target=next(i for i in r["ideas"] if i["keyword"]=="commercial roof repair cost")
    assert target["status"]=="EXACT_QUERY_PAGE_OBSERVED"
    assert target["observed_query_page_rows"][0]["reported_impressions"]==10
    assert target["observed_query_page_rows"][0]["reported_clicks"]==1
    assert target["observed_query_page_rows"][0]["gsc_reported_average_position"]==11.5
    assert target["keyword_search_volume"] is None
    assert target["demand_or_competition_score"] is None
    assert target["buyer_intent_verified"] is False
    assert r["gsc_query_page_sample_not_total_keyword_market"] is True
    assert r["attributed_revenue"] is None
    assert r["outbound_sent"] is False


def test_unmatched_real_search_is_retained_without_forcing_product_fit():
    r=review(packet(keyword="totally unrelated term"))
    assert r["exactly_observed_candidate_queries"]==0
    assert len(r["observed_other_queries"])==1
    assert r["observed_other_queries"][0]["review_state"]=="OBSERVED_NON_MATCH_NOT_DROPPED"
    assert all(x["status"]=="NOT_IN_RETURNED_GSC_SAMPLE" for x in r["ideas"])


@pytest.mark.parametrize("key,bad",[
    ("site_url","sc-domain:competitor.example"),
    ("source","not_google"),
    ("available",False),
])
def test_source_forgery_rejected(key,bad):
    v=packet();v[key]=bad
    with pytest.raises(KeywordGscEvidenceError,match="first_party"):
        review(v)


@pytest.mark.parametrize("transform",[
    lambda r: r.update(keys=["commercial roof repair cost"]),
    lambda r: r.update(keys=["commercial roof repair cost","https://bad.example/"]),
    lambda r: r.update(clicks=11),
    lambda r: r.update(impressions=-1),
    lambda r: r.update(ctr=2),
    lambda r: r.update(position=float("nan")),
])
def test_bad_query_page_or_metrics_rejected(transform):
    p=packet()
    transform(p["items"][0])
    with pytest.raises(KeywordGscEvidenceError):
        review(p)


def test_duplicate_query_page_pair_rejected():
    p=packet()
    p["items"].append(copy.deepcopy(p["items"][0]))
    p["count"]=2
    with pytest.raises(KeywordGscEvidenceError,match="duplicate"):
        review(p)


def test_finalised_short_window_required():
    with pytest.raises(KeywordGscEvidenceError,match="finalized"):
        review_gsc_keyword_ideas(research(),packet(),start=START,
                                 end=date(2026,10,25),today=TODAY)
    with pytest.raises(KeywordGscEvidenceError,match="finalized"):
        review_gsc_keyword_ideas(research(),packet(),start=START,
                                 end=date(2026,11,9),today=TODAY)


def test_bounded_existing_loopback_no_new_provider(monkeypatch):
    seen=[]
    def fake_transport(url):
        seen.append(url)
        return json.dumps(packet()).encode()
    r=read_original_loopback_gsc(research(),start=START,end=END,today=TODAY,
                                  transport=fake_transport)
    assert len(seen)==1
    assert seen[0].startswith("http://127.0.0.1:8771/v1/search/search-console/observations?")
    assert r["exactly_observed_candidate_queries"]==1
    assert r["paid_api_calls"]==0


def test_unavailable_data_fails_closed_without_zeros():
    x=read_original_loopback_gsc(research(),start=START,end=END,today=TODAY,
                                 transport=lambda _: b'bad-json')
    assert x["status"]=="HELD_GSC_QUERY_PAGE_SOURCE_UNAVAILABLE_OR_UNVERIFIED"
    assert x["estimated_search_volume"] is None
    assert x["observed_candidate_queries"] is None
    assert x["publishing_authorized"] is False
