from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import pytest

from empire_os.media_last30days_seo_review import (
    OUTPUT, build_seo_owner_review, refresh_seo_owner_review,
)
from empire_os.media_last30days_handoff import refresh_research_handoff

NOW=datetime(2026,10,27,23,0,tzinfo=timezone.utc)
URL="https://www.reddit.com/r/roofing/comments/12345/example"
REF="last30days:source:roofing-fixture"

def handoff():
    return {
        "schema_version":"empire.last30days.research_handoff.v1",
        "mode":"OBSERVE","generated_at":NOW.isoformat(),
        "execution_authority":"none","external_action_authorized":False,
        "database_write_authorized":False,"public_publish_authorized":False,
        "revenue_recognized":False,
        "buyer_intent_or_search_volume_from_engagement":False,
        "consumer_contracts":{"search_intelligence":{
            "status":"OWNER_REVIEW_ONLY",
            "search_rank_or_volume_proven":False,
            "automatic_index_or_content_changes_authorized":False}},
        "source_observation_count":2,"topic_count":1,
        "topics":[{
            "topic":"AI lead generation for roofing contractors",
            "candidate_observation_count":2,"observations":[
                {"source_ref":REF,"source_url":URL,"source_type":"reddit",
                 "rights":"PUBLIC_RESEARCH_REFERENCE_ONLY",
                 "published_at":NOW.isoformat(),"topic_relevance_verified":False,
                 "claim_verified":False,"buyer_intent_verified":False,
                 "source_text_executable":False,
                 "review_lane":"READ_TITLE_MATCH_FIRST_REQUIRES_HUMAN_CHECK",
                 "title_topic_match_candidate":True,"cross_topic_reused_reference":False},
                {"source_ref":"last30days:source:weak","source_url":"https://news.ycombinator.com/item?id=34",
                 "rights":"PUBLIC_RESEARCH_REFERENCE_ONLY",
                 "published_at":NOW.isoformat(),"topic_relevance_verified":False,
                 "claim_verified":False,"buyer_intent_verified":False,
                 "source_text_executable":False,
                 "review_lane":"CONTEXT_ONLY_WEAK_OR_OFF_TOPIC_TITLE",
                 "title_topic_match_candidate":False},
            ],
        }],
    }

def test_review_exports_only_citation_refs_not_unsupported_seo_metrics():
    d=build_seo_owner_review(handoff(),now=NOW)
    assert d["status"]=="REVIEW_CITATIONS_READY"
    assert d["review_first_unique_citation_count"]==1
    assert d["original_source_observation_count"]==2
    assert d["topics"][0]["references_for_manual_review"][0]["source_ref"]==REF
    assert d["topics"][0]["search_volume_or_rankings"] is None
    assert d["search_volume_verified"] is False
    assert d["publication_authorized"] is False
    assert d["seo_recommendation_accepted_by_owner"] is False
    assert d["automated_seo_changes_authorized"] is False
    assert "title" not in d["topics"][0]["references_for_manual_review"][0]

@pytest.mark.parametrize("url",[
    "http://www.reddit.com/example",
    "https://127.0.0.1/admin",
    "https://host.local/file",
    "https://www.reddit.com:abc/file",
    "https://user:pass@reddit.com/r",
    "https://www.reddit.com/r#fragment",
])
def test_unsafe_links_fail_closed(url):
    d=handoff();d["topics"][0]["observations"][0]["source_url"]=url
    with pytest.raises(ValueError,match="untrusted_reference"):
        build_seo_owner_review(d,now=NOW)

def test_stale_and_authorized_publication_rejected():
    d=handoff()
    with pytest.raises(ValueError,match="stale_research"):
        build_seo_owner_review(d,now=NOW+timedelta(hours=3))
    d["public_publish_authorized"]=True
    with pytest.raises(ValueError,match="not_authorized"):
        build_seo_owner_review(d,now=NOW)

def test_private_atomic_idempotent_update_does_not_create_seo_owner_system(tmp_path):
    d=handoff()
    result=refresh_seo_owner_review(tmp_path,d,now=NOW)
    target=tmp_path/OUTPUT
    assert result["seo_code_modified"] is False
    assert target.is_file() and target.stat().st_mode&0o777==0o600
    first=target.read_bytes()
    refresh_seo_owner_review(tmp_path,d,now=NOW)
    assert target.read_bytes()==first
    assert not (tmp_path/"empire_os/search_intelligence").exists()
    assert not (tmp_path/"runtime/search_intelligence").exists()

def test_existing_handoff_schedule_writes_private_seo_projection(tmp_path):
    queue={
        "schema_version":"empire.media.research_candidates.v1",
        "mode":"OBSERVE","execution_authority":"none","verified_claim_count":0,
        "script_ready_count":0,"public_publish_authorized":False,
        "automatic_script_generation_authorized":False,"actual_revenue":False,
        "candidate_count":1,"candidates":[{
            "schema_version":"empire.media.research_pack.v1",
            "research_id":"media-research:last30days:roofing",
            "topic":"AI lead generation for roofing contractors",
            "claims":[],"script_ready":False,"execution_authority":"none",
            "verified_claim_count":0,"public_publish_authorized":False,
            "sources":[{"source_ref":REF,"lineage_ref":URL}],
            "source_snippets":[{"source_ref":REF,"source_url":URL,
                "source":"reddit","title":"AI roofing contractor lead generation",
                "published_at":(NOW-timedelta(days=1)).isoformat()}],
        }],
    }
    result=refresh_research_handoff(tmp_path,queue,now=NOW)
    assert result["seo_owner_private_review"]["status"]=="REVIEW_CITATIONS_READY"
    seo=json.loads((tmp_path/OUTPUT).read_text())
    assert seo["review_first_unique_citation_count"]==1
    assert seo["execution_authority"]=="none"
    assert seo["owner"]=="ORIGINAL_SEARCH_INTELLIGENCE_IMPLEMENTATION_OWNER"
    assert seo["publication_authorized"] is False


def test_one_cycle_novelty_informs_owner_without_pretending_citation_was_reviewed(tmp_path):
    source=handoff()
    first=refresh_seo_owner_review(tmp_path,source,now=NOW)
    baseline=json.loads((tmp_path/OUTPUT).read_text())
    assert baseline["delta_review"]["comparison_available"] is False
    assert baseline["delta_review"]["new_since_previous_refresh_count"] is None
    assert first["new_since_previous_refresh"] is None
    # The same underlying source is refreshed later: no new citations.
    source["generated_at"]=(NOW+timedelta(minutes=30)).isoformat()
    source["topics"][0]["observations"].append({
        **source["topics"][0]["observations"][0],
        "source_ref":"last30days:source:new",
        "source_url":"https://www.reddit.com/r/roofing/comments/new/fresh",
    })
    source["source_observation_count"]=3
    source["topics"][0]["candidate_observation_count"]=3
    updated=refresh_seo_owner_review(tmp_path,source,now=NOW+timedelta(minutes=30))
    assert updated["new_since_previous_refresh"]==1
    assert updated["prior_snapshot_comparison_available"] is True
    new=json.loads((tmp_path/OUTPUT).read_text())
    assert new["delta_review"]["new_since_previous_refresh_count"]==1
    assert new["delta_review"]["already_present_previous_count"]==1
    cited=new["topics"][0]["references_for_manual_review"]
    assert [x["new_since_previous_refresh"] for x in cited]==[False,True]
    assert all(x["candidate_type"]=="UNVERIFIED_TITLE_MATCH_FOR_EDITORIAL_REVIEW" for x in cited)
    assert all("reviewed_at" not in x for x in cited)
    assert new["seo_recommendation_accepted_by_owner"] is False
    before=(tmp_path/OUTPUT).read_bytes()
    retried=refresh_seo_owner_review(tmp_path,source,now=NOW+timedelta(minutes=30))
    assert (tmp_path/OUTPUT).read_bytes()==before
    assert retried["new_since_previous_refresh"]==1


def test_stale_prior_cannot_prove_newness_and_future_prior_is_rejected():
    previous=build_seo_owner_review(handoff(),now=NOW)
    future=handoff()
    future["generated_at"]=(NOW+timedelta(days=3)).isoformat()
    result=build_seo_owner_review(future,now=NOW+timedelta(days=3),previous=previous)
    assert result["delta_review"]["comparison_available"] is False
    assert result["delta_review"]["new_since_previous_refresh_count"] is None
    with pytest.raises(ValueError,match="newer_than_current"):
        build_seo_owner_review(handoff(),now=NOW,previous={
            **previous,"source_handoff_generated_at":(NOW+timedelta(minutes=30)).isoformat(),
        })


def test_existing_review_corruption_never_overwritten(tmp_path):
    p=tmp_path/OUTPUT
    p.parent.mkdir(parents=True)
    p.write_text("untrusted data",encoding="utf-8")
    p.chmod(0o600)
    with pytest.raises(ValueError,match="unreadable_existing_private_review"):
        refresh_seo_owner_review(tmp_path,handoff(),now=NOW)
    assert p.read_text()=="untrusted data"
