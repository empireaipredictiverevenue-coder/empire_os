from datetime import datetime,timezone,timedelta

from empire_os.media_last30days_handoff import build_research_handoff
from empire_os.media_last30days_review_triage import (
    title_topic_match_candidate, TRIAGE_METHOD, REVIEW_FIRST, CONTEXT_ONLY,
)

NOW=datetime(2026,10,27,22,0,tzinfo=timezone.utc)


def pack(topic, entries):
    sources=[]; snippets=[]
    for i, (ref,title,url) in enumerate(entries):
        sources.append({"source_ref":ref,"lineage_ref":url})
        snippets.append({
            "source_ref":ref,"source":"hackernews",
            "source_url":url,"title":title,
            "published_at":(NOW-timedelta(days=2)).isoformat(),
        })
    return {
        "schema_version":"empire.media.research_pack.v1",
        "research_id":"media-research:last30days:"+topic.lower().replace(" ","-"),
        "topic":topic,"claims":[],"script_ready":False,
        "execution_authority":"none","public_publish_authorized":False,
        "verified_claim_count":0,
        "sources":sources,"source_snippets":snippets,
    }


def queue(*packs):
    return {
        "schema_version":"empire.media.research_candidates.v1",
        "mode":"OBSERVE","execution_authority":"none",
        "verified_claim_count":0,"script_ready_count":0,
        "public_publish_authorized":False,
        "automatic_script_generation_authorized":False,
        "actual_revenue":False,
        "candidate_count":len(packs),"candidates":list(packs),
    }


def test_conservative_title_matching_does_not_confuse_ai_with_roofing_leads():
    topic="AI lead generation for roofing contractors"
    assert not title_topic_match_candidate(topic,"Using thousands of AI agents to uncover new leads in biological data")
    assert not title_topic_match_candidate(topic,"AI use leads professor to drop homework grades")
    assert title_topic_match_candidate(topic,"Roofing contractor lead generation with first-party AI calls")
    assert not title_topic_match_candidate("unknown topic","roofing lead generation")
    assert not title_topic_match_candidate(topic,object())


def test_handoff_keeps_off_topic_citations_but_triages_relevance_without_approvals():
    topic="AI lead generation for roofing contractors"
    rows=[
        ("last30days:source:one","Roofing contractor lead generation with AI calls","https://news.ycombinator.com/item?id=1"),
        ("last30days:source:two","AI led to new cancer discovery in biology","https://news.ycombinator.com/item?id=2"),
    ]
    output=build_research_handoff(queue(pack(topic,rows)),now=NOW)
    entry=output["topics"][0]; obs=entry["observations"]
    assert len(obs)==2 and entry["candidate_observation_count"]==2
    assert [x["review_lane"] for x in obs]==[REVIEW_FIRST,CONTEXT_ONLY]
    assert [x["title_topic_match_candidate"] for x in obs]==[True,False]
    assert all(x["topic_relevance_verified"] is False and x["buyer_intent_verified"] is False for x in obs)
    assert "title" not in obs[0] and "summary" not in obs[0]
    assert output["review_triage"]["title_match_candidates_unverified"]==1
    assert output["review_triage"]["context_only_references"]==1
    assert output["review_triage"]["method"]==TRIAGE_METHOD
    assert output["review_triage"]["automatic_actions_authorized"] is False
    assert output["consumer_contracts"]["predictive_cloud"]["forecast_input_authorized"] is False
    assert output["public_publish_authorized"] is False


def test_cross_topic_repeated_url_does_not_count_as_independent_confirmation():
    url="https://news.ycombinator.com/item?id=12"
    ref="last30days:source:shared"
    first=pack("AI agents for small businesses",[(ref,"AI agents for small businesses",url)])
    second=pack("AI sales avatars and digital sales agents",[(ref,"AI sales avatars and digital sales agents",url)])
    output=build_research_handoff(queue(first,second),now=NOW)
    assert output["source_observation_count"]==2
    assert output["review_triage"]["cross_topic_reused_references"]==2
    assert all(t["observations"][0]["cross_topic_reused_reference"] for t in output["topics"])
    assert all(t["observations"][0]["claim_verified"] is False for t in output["topics"])


def test_unrelated_titles_not_promoted_into_economic_or_search_evidence():
    t="first-party revenue intelligence and attribution"
    output=build_research_handoff(queue(pack(t,[
        ("last30days:source:unrelated","Ukraine reports first drone evacuation","https://news.ycombinator.com/item?id=45")
    ])),now=NOW)
    assert output["review_triage"]["title_match_candidates_unverified"]==0
    assert output["topics"][0]["observations"][0]["review_lane"]==CONTEXT_ONLY
    assert output["consumer_contracts"]["search_intelligence"]["automatic_index_or_content_changes_authorized"] is False
    assert output["consumer_contracts"]["territory_radar"]["regional_buyer_demand_verified"] is False
