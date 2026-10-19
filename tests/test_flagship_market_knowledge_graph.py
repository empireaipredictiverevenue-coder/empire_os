"""Provenance-only market graph, approved scenario lessons, no chat scraping."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
import json
import pytest

from empire_os.flagship_market_knowledge_graph import (
    SCHEMA, build_market_knowledge_graph, prepare_market_conversation_brief,
)
from empire_os.community_intent_learning import source_id
from empire_os.icp_intent_source_atlas import SOURCES

NOW=datetime(2026,10,19,12,tzinfo=timezone.utc)


def sample(obs="https://www.reddit.com/r/agency/comments/a12345/an_example", *,
           niche="agency", pain=None, seen=NOW):
    return {
        "url":obs,"title":"Sensitive conversation example",
        "text":"Jane Doe 07700111222 pay me $10000 SECRET_API_KEY",
        "author":"Private Poster",
        "source":"reddit","niche":niche,"metro":"online",
        "observed_at":seen.isoformat(),
        "intent_band":"medium","intent_score":65,
        "pain_points":pain or ["lead_generation","sales_conversion"],
        "query":"expensive clients", "engagement":55,
        "evidence_urls":[obs],
    }


def fixture(tmp_path,rows=None,learning=None):
    base=tmp_path/"runtime/community_intent"
    base.mkdir(parents=True,exist_ok=True)
    obs=rows if rows is not None else [sample()]
    (base/"observations.json").write_text(json.dumps({
        "schema_version":"empire.community_intent_history.v1",
        "updated_at":NOW.isoformat(),"window_hours":96,
        "observations":obs,
    }))
    if learning is not None:
        (base/"source_learning_latest.json").write_text(json.dumps(learning))


def one_learning():
    s=next(x for x in SOURCES if x.source_id=="reddit_agency")
    return {
        "schema_version":"empire.icp_research_learning.v1",
        "mode":"OBSERVE","execution_authority":"NONE",
        "generated_at":NOW.isoformat(),
        "actual_revenue_learning":"REQUIRES_VERIFIED_CORTEX_AND_ECONOMIC_MEMORY",
        "source_results":[{
            "source_id":source_id((s.reddit_subreddit,s.reddit_query,s.niche,s.geography)),
            "attempted_cycles":2,"successful_retrievals":2,
            "new_posts":1,"seller_pitches":0,
            "operator_problems_unverified":1,
            "explicit_requests_unverified":1,
        }],
    }


def safe_example(*,ref="example_roofing_001", lesson="VERIFY_SERVICE_AREA",
                 niche="roofing",**changes):
    x={
        "example_ref":ref,
        "lesson_key":lesson,"niche":niche,
        "approval_class":"SYNTHETIC_SCENARIO",
        "human_approved":True,
        "reuse_permission":"INTERNAL_RETRIEVAL_ONLY",
        "contains_personal_data":False,
        "original_commercial_outcome_verified":False,
        "text_retained":False,
        "evidence_content_sha256":sha256(b"synthetic model-only example").hexdigest(),
    }
    x.update(changes)
    return x


def test_real_typed_graph_connects_atlas_posts_topics_products_without_contacts(tmp_path):
    fixture(tmp_path,learning=one_learning())
    g=build_market_knowledge_graph(tmp_path,as_of=NOW)
    assert g["schema_version"]==SCHEMA
    assert g["research_sources"]==14
    assert g["intelligence_data_products"]==8
    assert g["public_observations_indexed"]==1
    assert g["community_learning_health"]=="READ_ONLY_SOURCE_DIAGNOSTICS"
    assert g["community_source_diagnostic_rows"]==1
    assert g["node_count"]>25 and g["edge_count"]>35
    assert any(e["relation"]=="UNVERIFIED_TOPIC_TAG" for e in g["edges"])
    assert any(e["relation"]=="MAY_INFORM_DATA_PRODUCT" for e in g["edges"])
    assert all(e["claim_status"]=="CATEGORICAL_SOURCE_RELATION_NOT_BUYER_PROOF"
               for e in g["edges"])
    assert g["buyer_conversation_verified"] is False
    assert g["customer_roi_verified"] is False
    assert g["model_weights_updated"] is False
    assert g["customer_data_accessed"] is False
    assert g["external_crawler_run"] is False
    assert g["payment_authorized"] is False
    serialized=json.dumps(g)
    for secret in ("Jane Doe","07700111222","SECRET_API_KEY","Private Poster",
                   "Sensitive conversation example","a12345/an_example"):
        assert secret not in serialized


def test_market_brief_gives_only_sourced_topics_and_questions(tmp_path):
    fixture(tmp_path)
    g=build_market_knowledge_graph(tmp_path,as_of=NOW)
    brief=prepare_market_conversation_brief(g,niche="agency")
    assert brief["status"]=="PUBLIC_RESEARCH_BRIEF_NOT_COMMERCIAL_VERIFICATION"
    assert brief["public_observation_count"]==1
    assert set(topic["problem_theme"] for topic in brief["topics"])=={
        "lead_generation","sales_conversion"
    }
    assert all(t["truth_level"]=="UNVERIFIED_COMMUNITY_CLASSIFICATION"
               for t in brief["topics"])
    assert brief["buyer_proof"] is False
    assert brief["realized_revenue_proof"] is False
    unknown=prepare_market_conversation_brief(g,niche="unmapped_vertical")
    assert unknown["status"]=="MARKET_NOT_INDEXED"
    assert unknown["topics"]==[]


@pytest.mark.parametrize("url",[
    "http://www.reddit.com/r/agency/comments/a123/post",
    "https://evil.example/r/agency/comments/a123/post",
    "https://www.reddit.com.evil.example/r/agency/comments/a123/post",
    "https://someone:password@www.reddit.com/r/agency/comments/a123/post",
    "https://www.reddit.com:99999/r/agency/comments/a123/post",
    "https://www.reddit.com/r/agency/about/rules",
    "https://www.reddit.com/r/unknownsub/comments/a123/post",
    "https://www.reddit.com/r/sales/comments/a123/post",
])
def test_unlicensed_unsupported_or_wrong_source_is_quarantined(tmp_path,url):
    fixture(tmp_path,[sample(url)])
    report=build_market_knowledge_graph(tmp_path,as_of=NOW)
    assert report["public_observations_indexed"]==0
    assert report["unattributed_or_invalid_observations"]==1
    assert all(n["node_type"]!="public_observation" for n in report["nodes"])


def test_source_freshness_is_not_converted_into_success(tmp_path):
    fixture(tmp_path,[sample(seen=NOW-timedelta(days=15))])
    report=build_market_knowledge_graph(tmp_path,as_of=NOW)
    assert report["public_observations_indexed"]==0
    assert report["buyer_conversation_verified"] is False
    assert report["model_weights_updated"] is False


def test_duplicate_public_post_counted_once_even_if_retrieved_twice(tmp_path):
    fixture(tmp_path,[sample(),sample()])
    report=build_market_knowledge_graph(tmp_path,as_of=NOW)
    assert report["public_observations_indexed"]==1
    assert report["unattributed_or_invalid_observations"]==1


def test_unknown_source_learning_diagnostics_not_forged_into_atlas(tmp_path):
    d=one_learning()
    d["source_results"].append({
        **d["source_results"][0],"source_id":"sales|sales pipeline|b2b|online",
    })
    fixture(tmp_path,learning=d)
    g=build_market_knowledge_graph(tmp_path,as_of=NOW)
    assert g["community_source_diagnostic_rows"]==1
    assert g["unmapped_source_diagnostic_rows"]==1
    assert g["community_learning_health"]=="PARTIAL_SOURCE_DIAGNOSTICS_UNMAPPED_SOURCE_IDS"
    assert all(n["node_id"]!="research_source:sales" for n in g["nodes"])


def test_spoofed_source_learning_mode_does_not_leak_partial_diagnostics(tmp_path):
    d=one_learning()
    d["source_results"].append({
        **d["source_results"][0],"source_id":"fake@buyer.example",
        "attempted_cycles":True,
    })
    fixture(tmp_path,learning=d)
    g=build_market_knowledge_graph(tmp_path,as_of=NOW)
    assert g["community_source_diagnostic_rows"]==0
    assert g["community_learning_health"]=="HELD_UNTRUSTED_OR_STALE"
    assert "fake@buyer.example" not in json.dumps(g)


def test_approved_synthetic_lessons_are_retrievable_but_no_transcript_or_training(tmp_path):
    fixture(tmp_path)
    g=build_market_knowledge_graph(tmp_path,as_of=NOW,
                                   approved_examples=[safe_example()])
    assert g["approved_scenario_lessons"]==1
    assert any(e["relation"]=="EXAMPLE_ILLUSTRATES_THEME" for e in g["edges"])
    brief=prepare_market_conversation_brief(g,niche="roofing")
    assert "VERIFY_SERVICE_AREA" in brief["lessons"]
    assert brief["no_training_on_private_chats"] is True
    assert g["model_weights_updated"] is False
    assert g["community_text_reused_for_training"] is False


@pytest.mark.parametrize("changes",[
    {"human_approved":False},
    {"reuse_permission":"TRAIN_MODEL_WEIGHTS"},
    {"contains_personal_data":True},
    {"original_commercial_outcome_verified":True},
    {"text_retained":True},
    {"approval_class":"PRIVATE_CONVERSATION"},
    {"evidence_content_sha256":"unknown"},
    {"lesson_key":"SEND_OUTBOUND"},
    {"example_ref":"buyer@example.com"},
    {"niche":"roofing","customer_name":"PRIVATE"},
])
def test_chat_examples_without_explicit_safe_curation_never_enter_graph(tmp_path,changes):
    fixture(tmp_path)
    with pytest.raises(ValueError):
        build_market_knowledge_graph(tmp_path,as_of=NOW,
                                     approved_examples=[safe_example(**changes)])


def test_example_conflicting_duplicate_blocks_not_overwritten(tmp_path):
    fixture(tmp_path)
    with pytest.raises(ValueError,match="conflicting graph node"):
        build_market_knowledge_graph(
            tmp_path,as_of=NOW,
            approved_examples=[
                safe_example(),
                safe_example(lesson="VERIFY_DELIVERY_CAPACITY")
            ])


def test_empty_source_files_dont_become_verified_zero(tmp_path):
    graph=build_market_knowledge_graph(tmp_path,as_of=NOW)
    assert graph["public_research_health"]=="UNAVAILABLE"
    assert graph["community_learning_health"]=="UNAVAILABLE"
    assert graph["buyer_conversation_verified"] is False
    assert graph["customer_roi_verified"] is False
    assert graph["node_count"]>0


def test_read_only_graph_is_deterministic_given_same_sources_and_clock(tmp_path):
    fixture(tmp_path,learning=one_learning())
    x=build_market_knowledge_graph(tmp_path,as_of=NOW)
    y=build_market_knowledge_graph(tmp_path,as_of=NOW)
    assert x==y
    assert not (tmp_path/"new_database").exists()


def test_market_agent_preparation_questions_follow_existing_knowledge_taxonomy(tmp_path):
    fixture(tmp_path)
    graph=build_market_knowledge_graph(tmp_path,as_of=NOW)
    brief=prepare_market_conversation_brief(graph,niche="agency")
    questions={item["problem_theme"]:item["next_human_question"]
               for item in brief["topics"]}
    assert "qualified enquiries" in questions["lead_generation"]
    assert "accepted commercial offer" in questions["sales_conversion"]
    assert "organic search" in questions["search_visibility"] if "search_visibility" in questions else True
    assert all(item["existing_source_research_next_action"]
               for item in brief["topics"])
    assert brief["buyer_proof"] is False


def test_approved_private_example_manifest_import_requires_secure_custody(
    tmp_path,monkeypatch
):
    from scripts import review_flagship_market_knowledge_20261019 as command
    private=tmp_path/"runtime/knowledge_graph/approved_examples.json"
    private.parent.mkdir(parents=True)
    monkeypatch.setattr(command,"CURATED",private)
    manifest={"schema_version":"empire.knowledge_graph.curated_scenarios.v1",
              "human_reviewed":True,"examples":[safe_example()]}
    private.write_text(json.dumps(manifest))
    private.chmod(0o600)
    assert len(command._read_curated())==1
    private.chmod(0o644)
    with pytest.raises(ValueError,match="strict custody"):
        command._read_curated()
    private.chmod(0o600)
    manifest["examples"][0]["raw_conversation_text"]="PRIVATE CUSTOMER EMAIL"
    private.write_text(json.dumps(manifest))
    assert "raw_conversation_text" in command._read_curated()[0]
    # Raw transcript rejection happens in the independently validated
    # graph builder: never assume a manifest-level human approval is enough.
    with pytest.raises(ValueError,match="approved example schema"):
        build_market_knowledge_graph(tmp_path,as_of=NOW,
                                     approved_examples=command._read_curated())


def test_identical_approved_example_replay_does_not_inflate_learning_count(tmp_path):
    fixture(tmp_path)
    one=safe_example()
    graph=build_market_knowledge_graph(tmp_path,as_of=NOW,
        approved_examples=[one,deepcopy(one)])
    assert graph["approved_scenario_lessons"]==1
    assert sum(n["node_type"]=="approved_example" for n in graph["nodes"])==1
