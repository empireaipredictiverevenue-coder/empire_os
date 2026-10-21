from datetime import datetime, timezone

import pytest

from empire_os.icp_intent_source_atlas import (
    SOURCES, REDDIT_ROTATION, atlas_summary,
)
from empire_os.icp_intent_relevance import classify_icp_intent
from empire_os.commercial_social_intent import build_social_intent_review
from scripts import run_community_intent_cycle as cycle


NOW = datetime(2026, 10, 9, 21, tzinfo=timezone.utc)


def test_icp_atlas_adds_verified_communities_to_current_reddit_rotation():
    atlas = atlas_summary()
    assert atlas["source_count"] >= 14
    assert atlas["automatic_public_rss_sources"] >= 11
    assert atlas["manual_review_only_sources"] >= 3
    assert atlas["private_or_login_gated_scraping_enabled"] is False
    assert atlas["outbound_authorized"] is False
    ids = {s.source_id for s in SOURCES}
    assert len(ids) == len(SOURCES)
    assert {"reddit_roofing_sales", "reddit_leadgen_marketplace",
            "reddit_hvacpeople", "reddit_lawfirm"} <= ids
    assert ("RoofingSales", "marketing leads", "roofing", "US") in REDDIT_ROTATION
    assert ("LeadGenMarketplace", "roofing leads", "roofing", "US") in REDDIT_ROTATION
    assert set(REDDIT_ROTATION) <= set(cycle.REDDIT_ROTATION)
    assert ("Dentistry", "new patients marketing", "dental", "US") in REDDIT_ROTATION
    assert ("SaaS", "struggling get customers", "saas", "online") in REDDIT_ROTATION
    assert sum(x[0] == "Dentistry" for x in REDDIT_ROTATION) == 1
    assert sum(x[0] == "SaaS" for x in REDDIT_ROTATION) == 1
    for source in SOURCES:
        assert source.url.startswith("https://")
        if source.venue != "Reddit":
            assert source.automation_state == "MANUAL_REVIEW_ONLY"
        assert source.to_dict()["outbound_authorized"] is False


@pytest.mark.parametrize(("text", "expected"), [
    ("We run a roofing company and need more qualified appointments",
     "EXPLICIT_REQUEST_UNVERIFIED"),
    ("Looking for a company that sells roofing leads in Texas",
     "EXPLICIT_REQUEST_UNVERIFIED"),
    ("Our roofing business spends too much on Google ads",
     "OPERATOR_PROBLEM_SELF_REPORTED"),
    ("We help roofing companies buy leads. DM me today!",
     "SELLER_PITCH"),
    ("Here is how to generate more leads: 5 tips",
     "CONTENT_OR_ADVICE"),
    ("Growth and revenue are important for companies",
     "UNATTRIBUTED_DISCUSSION"),
])
def test_problem_vs_seller_distinction(text, expected):
    r = classify_icp_intent({
        "title": text,
        "pain_points": ["lead_generation", "search_visibility"],
    })
    assert r["intent_class"] == expected
    assert r["operator_identity_verified"] is False
    assert r["buyer_purchase_intent_verified"] is False
    assert r["outbound_authorized"] is False
    assert r["candidate_offer_hypotheses"]


def test_social_qualifications_do_not_activate_buyer_or_email():
    now=NOW.isoformat()
    inbox={
        "a":{
            "source":"reddit_intent","status":"unresolved",
            "url":"https://reddit.com/r/RoofingSales/comments/abc",
            "raw":{"community_intent":{
                "observed_at":now,
                "title":"Need a reputable roofing leads company",
                "text":"We run a roofing company and need more qualified appointments",
                "intent_score":76,
                "pain_points":["lead_generation","sales_conversion"],
                "url":"https://reddit.com/r/RoofingSales/comments/abc",
            }},
        },
        "b":{
            "source":"linkedin_intent","status":"unresolved",
            "url":"https://linkedin.com/posts/abc",
            "raw":{"community_intent":{
                "observed_at":now,
                "title":"We help roofing contractors and sell leads",
                "text":"DM me to book a call",
                "intent_score":85,
                "pain_points":["lead_generation"],
                "url":"https://linkedin.com/posts/abc",
            }},
        },
    }
    r=build_social_intent_review(inbox,[],now=NOW)
    assert r["sources"] == {"reddit_intent":1,"linkedin_intent":1}
    assert r["intent_class_counts"]["EXPLICIT_REQUEST_UNVERIFIED"]==1
    assert r["intent_class_counts"]["SELLER_PITCH"]==1
    assert r["candidate_offer_interest_signals"]==[
        {"offer_key":"predictive_revenue_demand_engine",
         "signal_observations":1,"paid_demand_verified":False},
        {"offer_key":"revenue_conversion_system",
         "signal_observations":1,"paid_demand_verified":False},
    ]
    assert r["verified_commercial_buying_intent_count"]==0
    assert all(x["outbound_authorized"] is False
               for x in r["identity_unverified_review_queue"])


def test_linkedin_source_circuit_open_not_false_fresh(monkeypatch):
    monkeypatch.setattr(cycle,"search_reliable",lambda *args,**kwargs:{
        "organic":[], "error":"Public discovery circuit open",
        "searchParameters":{
            "engine":"public_recovery","search_state":"PROVIDER_DEGRADED",
            "circuit_open":True,
        },
        "search_operational_status":"CIRCUIT_OPEN",
    })
    rows,status=cycle._collect_linkedin(
        "need roofing leads","roofing","US",
    )
    assert rows==[]
    assert status["ok"] is False
    assert status["circuit_open"] is True
    assert status["search_operational_status"]=="CIRCUIT_OPEN"


def test_cached_linkedin_posts_never_republished_as_new_signals(monkeypatch):
    monkeypatch.setattr(cycle,"search_reliable",lambda *args,**kwargs:{
        "organic":[{
            "title":"Looking for sales automation recommendations",
            "link":"https://www.linkedin.com/posts/example",
            "snippet":"Need help with leads and client acquisition",
        }],
        "error":None,
        "searchParameters":{
            "engine":"public_recovery","search_state":"STALE_RESULTS",
            "stale_cache":True,"cache":True,
        },
        "search_operational_status":"DEGRADED_WITH_LAST_KNOWN_GOOD",
    })
    rows,status=cycle._collect_linkedin("need sales automation","b2b","online")
    assert rows==[]
    assert status["ok"] is False
    assert status["cached_results_rejected_as_live"] is True
    assert status["accepted_observations"]==0


def test_fresh_linkedin_search_still_emits_only_observations(monkeypatch):
    monkeypatch.setattr(cycle,"search_reliable",lambda *args,**kwargs:{
        "organic":[{
            "title":"Looking for sales automation recommendations",
            "link":"https://www.linkedin.com/posts/example",
            "snippet":"Our manual follow up is costing us leads",
        }],
        "searchParameters":{"engine":"public_recovery",
                            "search_state":"RESULTS","cache":False},
        "error":None,
    })
    rows,status=cycle._collect_linkedin("need sales automation","b2b","online")
    assert status["ok"] is True
    assert len(rows)==1
    assert rows[0].source=="linkedin"
    assert rows[0].intent_score>=35


@pytest.mark.parametrize("malicious", [
    "https://linkedin.com.evil.example/posts/abc",
    "https://notlinkedin.com/posts/abc",
    "https://evil.example/linkedin.com/posts/abc",
    "https://reddit.com.evil.example/r/sales/comments/abc",
    "https://[bad-ipv6/r/sales/comments/abc",
])
def test_platform_lookalikes_cannot_enter_intent_pipeline(malicious):
    from empire_os.community_intent import normalize_search_result
    platform = "reddit" if "reddit" in malicious else "linkedin"
    observation = normalize_search_result(
        platform=platform, query="leads",
        result={
            "title":"Need new leads",
            "link":malicious,
            "snippet":"I run a business and want more customers",
        },
    )
    assert observation is None
