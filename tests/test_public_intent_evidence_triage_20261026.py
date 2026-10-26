"""Rank RESEARCH ACTIONS, never invent customer demand."""
from datetime import date
import pytest

from empire_os.public_intent_offer_method_bridge import (
    IntentOfferSpec,prepare_public_intent_offer_review,
)
from empire_os.public_intent_gsc_evidence_bridge import review_gsc_keyword_ideas
from empire_os.public_intent_evidence_triage import build_intent_evidence_review_queue

START=date(2026,10,4)
END=date(2026,10,16)
TODAY=date(2026,10,26)


def seed():
    return prepare_public_intent_offer_review(IntentOfferSpec(
        market_key="revenue",
        seed_keyword="revenue evidence",
        icp_key="enterprise-buyer",
        buyer_problem="Know whether a sales opportunity is genuinely progressing",
    ))


def sample():
    return {"source":"google_search_console","site_url":"sc-domain:empire-ai.co.uk",
            "available":True,"count":1,"limit":25,
            "items":[{"keys":["revenue evidence cost",
                     "https://empire-ai.co.uk/predictive-revenue"],
                      "clicks":0,"impressions":1,"ctr":0.0,"position":10.0}]}


def test_actual_observed_query_is_reviewed_first_not_auto_published():
    x=seed()
    g=review_gsc_keyword_ideas(x,sample(),start=START,end=END,today=TODAY)
    q=build_intent_evidence_review_queue(x,g)
    assert q["candidate_count"]==len(x["keyword_candidates"])
    assert q["first_party_exact_match_count"]==1
    assert q["priority_ordered_candidates"][0]["keyword"]=="revenue evidence cost"
    assert q["priority_ordered_candidates"][0]["priority"]=="P1_REVIEW_FIRST_PARTY_QUERY_MATCH"
    assert q["priority_ordered_candidates"][0]["observed_query_page_rows"][0]["reported_impressions"]==1
    assert q["priority_ordered_candidates"][0]["commercial_buyer_verified"] is False
    assert q["economic_priority_score"] is None
    assert q["auto_publish"] is False
    assert q["database_writes"] is False


def test_zero_matching_observed_rows_cannot_be_counted_as_demand():
    x=seed()
    g=review_gsc_keyword_ideas(
        x,{**sample(),"items":[{**sample()["items"][0],"keys":["other keyword",
            "https://empire-ai.co.uk/"]}]},
        start=START,end=END,today=TODAY,
    )
    q=build_intent_evidence_review_queue(x,g)
    assert q["first_party_exact_match_count"]==0
    assert all(not row["observed_first_party_query"] for row in q["priority_ordered_candidates"])
    assert all(row["search_volume"] is None for row in q["priority_ordered_candidates"])
    assert all(row["keyword_difficulty"] is None for row in q["priority_ordered_candidates"])
    assert all(row["next_action"]=="OBTAIN_ORIGINAL_SERP_OR_FIRST_PARTY_QUERY_EVIDENCE"
               for row in q["priority_ordered_candidates"])


def test_without_gsc_only_hypothesis_review_order_exists():
    q=build_intent_evidence_review_queue(seed())
    assert q["source_gsc_review_available"] is False
    assert q["first_party_exact_match_count"]==0
    assert q["revenue_claimed"] is False


def test_foreign_unverified_packet_rejected():
    with pytest.raises(ValueError,match="canonical_gsc"):
        build_intent_evidence_review_queue(seed(),{"schema_version":"fake"})
