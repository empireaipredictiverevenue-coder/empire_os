"""God's Eye may display research references, but cannot turn them into leads."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from empire_os.godseye_last30days_context import (
    SCHEMA, OUTPUT, build_godseye_research_context,
    refresh_godseye_research_context,
)
from empire_os.media_last30days_handoff import refresh_research_handoff

NOW = datetime.now(timezone.utc)


def source():
    return {
        "schema_version": "empire.last30days.research_handoff.v1",
        "generated_at": NOW.isoformat(),
        "mode": "OBSERVE", "execution_authority": "none",
        "external_action_authorized": False,
        "public_publish_authorized": False,
        "revenue_recognized": False,
        "buyer_intent_or_search_volume_from_engagement": False,
        "topic_count": 1, "source_observation_count": 1,
        "topics": [{
            "topic": "AI lead generation for roofing contractors",
            "candidate_observation_count": 1,
            "review_status": "REQUIRES_INDEPENDENT_TOPIC_RELEVANCE_AND_FACT_CHECK",
            "observations": [{
                "source_type": "reddit",
                "source_url": "https://www.reddit.com/r/roofing/comments/id123/example",
                "published_at": (NOW-timedelta(days=1)).isoformat(),
                "rights": "PUBLIC_RESEARCH_REFERENCE_ONLY",
                "topic_relevance_verified": False,
                "claim_verified": False,
                "buyer_intent_verified": False,
                "local_geography_verified": False,
                "source_text_executable": False,
            }],
        }],
    }


def test_claimless_godseye_context_has_no_fake_geographic_pins_or_sales():
    result=build_godseye_research_context(source(),now=NOW)
    assert result["schema_version"] == SCHEMA
    assert result["topic_count"] == 1
    assert result["source_observation_count"] == 1
    assert result["topics"][0]["citations_for_review"][0]["topic_relevance_verified"] is False
    assert result["geographic_coordinates_verified"] is False
    assert result["forecast_or_commercial_buyer_verified"] is False
    assert result["display_scope"] == "RESEARCH_PANEL_ONLY_NOT_MAP_MARKERS"
    assert result["public_publish_authorized"] is False
    assert not any("coordinates" in x for x in result["topics"])


def test_stale_or_untrusted_handoff_is_never_displayed():
    d=source()
    d["generated_at"]=(NOW-timedelta(hours=3)).isoformat()
    with pytest.raises(ValueError,match="untrusted_or_stale"):
        build_godseye_research_context(d,now=NOW)
    d=source()
    d["public_publish_authorized"]=True
    with pytest.raises(ValueError,match="untrusted_or_stale"):
        build_godseye_research_context(d,now=NOW)


def test_non_https_private_url_never_enters_panel():
    d=source()
    d["topics"][0]["observations"][0]["source_url"]="http://localhost/admin"
    result=build_godseye_research_context(d,now=NOW)
    assert result["topics"][0]["citations_for_review"]==[]
    assert result["excluded_reference_count"]==1


def test_deduplicated_topic_ids_and_source_counts_must_match():
    d=source()
    d["source_observation_count"]=2
    with pytest.raises(ValueError,match="source_count"):
        build_godseye_research_context(d,now=NOW)


def test_private_atomic_review_only_and_repeated_update(tmp_path):
    first=refresh_godseye_research_context(tmp_path,source(),now=NOW)
    p=tmp_path/OUTPUT
    assert p.is_file() and first["map_markers_created"]==0
    assert (p.stat().st_mode & 0o777)==0o600
    before=json.loads(p.read_text())
    again=refresh_godseye_research_context(tmp_path,source(),now=NOW)
    assert json.loads(p.read_text())==before
    assert again["citations_for_review"]==1


def test_existing_media_handoff_writes_private_review_via_one_owner(tmp_path):
    """The original Media OS producer remains sole owner of both artifacts."""
    # Small but fully safe canonical Media OS candidate.
    candidate={
        "schema_version":"empire.media.research_pack.v1",
        "research_id":"media-research:last30days:sample",
        "topic":"AI lead generation for roofing contractors",
        "sources":[{
            "source_ref":"last30days:source:abc", "lineage_ref":"https://www.reddit.com/r/roofing/comments/abc/test",
        }],
        "source_snippets":[{
            "source_ref":"last30days:source:abc",
            "source":"reddit",
            "source_url":"https://www.reddit.com/r/roofing/comments/abc/test",
            "published_at":(NOW-timedelta(days=1)).isoformat(),
        }],
        "claims":[], "verified_claim_count":0, "script_ready":False,
        "public_publish_authorized":False,
        "execution_authority":"none",
    }
    queue={
        "schema_version":"empire.media.research_candidates.v1",
        "mode":"OBSERVE","execution_authority":"none",
        "verified_claim_count":0,"script_ready_count":0,
        "automatic_script_generation_authorized":False,
        "public_publish_authorized":False,"actual_revenue":False,
        "candidate_count":1,"candidates":[candidate],
    }
    result=refresh_research_handoff(tmp_path,queue,now=NOW)
    assert result["godseye_private_review"]["topics"]==1
    assert json.loads((tmp_path/OUTPUT).read_text())["topic_count"]==1
    assert result["godseye_private_review"]["map_markers_created"]==0
