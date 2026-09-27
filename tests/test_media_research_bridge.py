import json

from empire_os.media_research_bridge import (
    build_media_research_candidates,
    refresh_media_research_bridge,
)


def research_payload():
    return {
        "schema_version": "empire.opportunity_research_batch.v1",
        "mode": "OBSERVE",
        "generated_at": "2026-09-23T14:00:00+00:00",
        "actions": [
            {
                "opportunity_key": "community_pain:search_visibility",
                "opportunity_class": "community_pain",
                "title": "Search Visibility",
                "planned_query_count": 2,
                "queries": [
                    '"Search Visibility" businesses',
                    '"Search Visibility" software service',
                ],
                "observations": [
                    {
                        "query": '"Search Visibility" businesses',
                        "observation_type": "public_search_result",
                        "title": "Example result",
                        "snippet": "Observed public snippet",
                        "url": "https://example.test/a",
                        "verified_fact": False,
                    },
                    {
                        "query": '"Search Visibility" software service',
                        "observation_type": "public_search_result",
                        "title": "Second result",
                        "snippet": "Second observed snippet",
                        "url": "https://example.test/b",
                        "verified_fact": False,
                    },
                ],
            }
        ],
        "execution_authority": "none",
    }


def test_research_bridge_creates_claimless_evidence_pack():
    result = build_media_research_candidates(research_payload())

    assert result["source_available"] is True
    assert result["candidate_count"] == 1
    assert result["source_observation_count"] == 2
    assert result["verified_claim_count"] == 0
    assert result["script_ready_count"] == 0
    assert result["search_observations_are_verified_facts"] is False

    pack = result["candidates"][0]
    assert pack["topic"] == "Search Visibility"
    assert pack["claims"] == []
    assert len(pack["sources"]) == 2
    assert pack["source_observation_count"] == 2
    assert pack["verified_claim_count"] == 0
    assert pack["claim_verification_required"] is True
    assert pack["script_ready"] is False
    assert pack["source_observations_are_verified_facts"] is False
    assert pack["automatic_script_generation_authorized"] is False
    assert pack["public_publish_authorized"] is False
    assert pack["execution_authority"] == "none"


def test_missing_research_stays_unavailable():
    result = build_media_research_candidates(None)

    assert result["source_available"] is False
    assert result["candidate_count"] == 0
    assert result["verified_claim_count"] == 0
    assert result["script_ready_count"] == 0


def test_refresh_writes_only_media_runtime_input(tmp_path):
    source = tmp_path / "runtime/opportunity_radar/research_latest.json"
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps(research_payload()))

    result = refresh_media_research_bridge(tmp_path)

    assert result["candidate_count"] == 1
    assert result["external_action_performed"] is False
    assert result["database_write_performed"] is False

    path = (
        tmp_path
        / "runtime/media_os/input/research_pack_candidates.json"
    )
    assert path.exists()

    saved = json.loads(path.read_text())
    assert saved["candidate_count"] == 1
    assert saved["verified_claim_count"] == 0
    assert saved["automatic_script_generation_authorized"] is False
    assert saved["execution_authority"] == "none"
