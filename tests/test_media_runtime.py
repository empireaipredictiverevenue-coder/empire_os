import json
from pathlib import Path

from empire_os.media_runtime import (
    build_media_os_runtime,
    refresh_media_os_runtime,
)


def write_json(root: Path, relative: str, payload) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def seed_real_media_inputs(root: Path) -> None:
    write_json(
        root,
        "runtime/media_os/input/youtube_public_observations.json",
        {
            "observations": [
                {
                    "id": "v1",
                    "channel_id": "public-channel-1",
                    "title": "Baseline 1",
                    "views": 100,
                    "evidence_refs": ["youtube:public:v1"],
                },
                {
                    "id": "v2",
                    "channel_id": "public-channel-1",
                    "title": "Baseline 2",
                    "views": 100,
                    "evidence_refs": ["youtube:public:v2"],
                },
                {
                    "id": "v3",
                    "channel_id": "public-channel-1",
                    "title": "Baseline 3",
                    "views": 100,
                    "evidence_refs": ["youtube:public:v3"],
                },
                {
                    "id": "v4",
                    "channel_id": "public-channel-1",
                    "title": "Observed breakout",
                    "views": 500,
                    "evidence_refs": ["youtube:public:v4"],
                },
            ]
        },
    )
    write_json(
        root,
        "runtime/media_os/input/youtube_owned_analytics.json",
        {
            "observations": [
                {
                    "video_id": "owned-v1",
                    "surface": "BROWSE",
                    "impressions": 10000,
                    "views": 900,
                    "engaged_views": 700,
                    "watch_time_minutes": 4000,
                    "average_view_percentage": 0.58,
                    "subscribers_gained": 30,
                    "audience_cluster_ref": "audience:founders",
                    "evidence_refs": ["youtube:analytics:owned-v1:browse"],
                },
                {
                    "video_id": "owned-v1",
                    "surface": "SUGGESTED",
                    "source_video_id": "source-video-1",
                    "impressions": 4000,
                    "views": 500,
                    "engaged_views": 410,
                    "watch_time_minutes": 2300,
                    "average_view_percentage": 0.63,
                    "subscribers_gained": 22,
                    "audience_cluster_ref": "audience:founders",
                    "evidence_refs": ["youtube:analytics:owned-v1:suggested"],
                },
            ]
        },
    )
    write_json(
        root,
        "runtime/media_os/input/youtube_owned_video_metrics.json",
        {
            "records": [
                {
                    "channel_id": "owned-channel",
                    "video_id": "owned-v1",
                    "views": 1400,
                    "engaged_views": 1110,
                    "watch_time_minutes": 6300,
                    "average_view_duration_seconds": 270,
                    "average_view_percentage": 0.60,
                    "subscribers_gained": 52,
                    "subscribers_lost": 3,
                    "evidence_refs": [
                        "youtube:analytics:owned-v1:summary"
                    ],
                }
            ]
        },
    )
    write_json(
        root,
        "runtime/media_os/input/trend_signals.json",
        {
            "signals": [
                {
                    "topic": "AI lead generation",
                    "source_family": "youtube",
                    "velocity": 0.7,
                    "evidence_refs": ["youtube:trend:1"],
                },
                {
                    "topic": "AI lead generation",
                    "source_family": "search",
                    "velocity": 0.5,
                    "evidence_refs": ["search:trend:1"],
                },
                {
                    "topic": "AI lead generation",
                    "source_family": "community",
                    "velocity": 0.4,
                    "evidence_refs": ["community:trend:1"],
                },
            ]
        },
    )
    write_json(
        root,
        "runtime/media_os/input/build_journal.json",
        {
            "items": [
                {
                    "entry_id": "build:1",
                    "system": "Media OS",
                    "change": "Added Algorithm Intelligence",
                    "problem": "Distribution learning was missing.",
                    "solution": "Added evidence-based surface analysis.",
                    "evidence_refs": ["commit:algorithm-intelligence"],
                    "novelty_observed": True,
                    "audience_relevance_observed": True,
                    "demonstration_available": True,
                    "commercial_relevance_observed": True,
                }
            ]
        },
    )
    write_json(
        root,
        "runtime/media_os/input/idea_candidates.json",
        {
            "candidates": [
                {
                    "idea_id": "idea:algorithm-engine",
                    "topic": "How YouTube Distribution Actually Looks in Data",
                    "angle": "Build an evidence-driven algorithm engine without pretending to know private weights.",
                    "audience": "founders",
                    "evidence_refs": [
                        "commit:algorithm-intelligence",
                        "youtube:analytics:owned-v1:browse",
                    ],
                    "source_systems": [
                        "media_os",
                        "youtube_intelligence",
                    ],
                    "format_candidates": [
                        "build_in_public",
                        "tutorial",
                    ],
                    "opportunity_features": {
                        "empire_expertise": 1.0,
                        "audience_fit": 0.8,
                        "strategic_relevance": 1.0,
                        "production_feasibility": 0.9,
                    },
                }
            ]
        },
    )


def test_runtime_with_no_inputs_does_not_invent_evidence(tmp_path):
    result = build_media_os_runtime(tmp_path)

    assert result["runtime_active"] is True
    assert result["observed_source_count"] == 0
    assert result["real_evidence_present"] is False
    assert result["youtube_public"]["observation_count"] == 0
    assert result["idea_backlog"]["candidate_count"] == 0
    assert result["ready_for_research_generation"] is False
    assert result["channel"]["external_youtube_channel_id"] is None
    assert result["public_publish_authorized"] is False
    assert result["external_action_performed"] is False
    assert result["database_write_performed"] is False
    assert result["actual_revenue"] is False
    assert result["execution_authority"] == "none"


def test_runtime_ingests_real_evidence_and_builds_internal_backlog(tmp_path):
    seed_real_media_inputs(tmp_path)
    result = build_media_os_runtime(tmp_path)

    assert result["observed_source_count"] == 6
    assert result["real_evidence_present"] is True

    youtube = result["youtube_public"]
    assert youtube["observation_count"] == 4
    assert youtube["channel_baseline_count"] == 1
    assert youtube["outliers"]["candidate_count"] == 1
    assert youtube["outliers"]["candidates"][0]["video_id"] == "v4"

    owned = result["owned_video_metrics"]
    assert owned["record_count"] == 1
    assert owned["observed_totals"]["views"] == 1400.0
    assert owned["observed_totals"]["subscribers_gained"] == 52.0
    assert owned["actual_revenue"] is False

    algorithm = result["algorithm_intelligence"]
    assert algorithm["observation_count"] == 2
    assert algorithm["distribution"]["surface_count"] == 2
    assert algorithm["recommendation_chain"]["edge_count"] == 1
    assert algorithm["hypothesis_count"] == 1
    assert (
        algorithm["hypotheses"][0]["private_algorithm_weights_known"]
        is False
    )

    trends = result["trend_fusion"]
    assert trends["topic_count"] == 1
    assert (
        trends["topics"][0]["trend_state"]
        == "MULTISOURCE_ACCELERATION"
    )

    assert result["build_journal"]["opportunity_candidate_count"] == 1

    ideas = result["idea_backlog"]
    assert ideas["candidate_count"] == 1
    assert ideas["pending_quant_review_count"] == 1
    assert ideas["scored_candidate_count"] == 0
    assert ideas["candidates"][0]["decision"] == "PENDING_QUANT_REVIEW"

    assert result["ready_for_research_generation"] is True
    assert result["public_publish_authorized"] is False
    assert result["actual_revenue"] is False


def test_refresh_writes_only_runtime_status_artifact(tmp_path):
    seed_real_media_inputs(tmp_path)
    result = refresh_media_os_runtime(tmp_path)

    path = tmp_path / "runtime/media_os/latest.json"
    assert path.exists()

    saved = json.loads(path.read_text())
    assert saved["schema_version"] == "empire.media_os.runtime.v1"
    assert saved["generated_at"] == result["generated_at"]
    assert saved["database_write_performed"] is False
    assert saved["external_action_performed"] is False
    assert saved["execution_authority"] == "none"


def test_runtime_merges_empire_bridge_inputs_without_overwriting_manual_inputs(
    tmp_path,
):
    write_json(
        tmp_path,
        "runtime/media_os/input/idea_candidates.json",
        {
            "candidates": [
                {
                    "idea_id": "manual:1",
                    "topic": "Manual media idea",
                    "angle": "A manually prepared idea",
                    "audience": "founders",
                    "evidence_refs": ["manual:evidence:1"],
                    "source_systems": ["media_os"],
                    "opportunity_features": {},
                }
            ]
        },
    )
    write_json(
        tmp_path,
        "runtime/media_os/input/empire_opportunity_ideas.json",
        {
            "candidates": [
                {
                    "idea_id": "empire:1",
                    "topic": "Observed community pain",
                    "angle": "Evidence-led community analysis",
                    "audience": "founders and operators",
                    "evidence_refs": ["community:evidence:1"],
                    "source_systems": [
                        "opportunity_radar",
                        "community_intent",
                    ],
                    "opportunity_features": {},
                    "opportunity_refs": ["community_pain:test"],
                    "quant_packet_ref": (
                        "opportunity_quant_review:community_pain:test"
                    ),
                    "quant_packet_status": "AVAILABLE",
                    "commercial_quant_is_media_score": False,
                }
            ]
        },
    )
    write_json(
        tmp_path,
        "runtime/media_os/input/empire_build_journal.json",
        {
            "items": [
                {
                    "entry_id": "git:abc",
                    "system": "EmpireOS",
                    "change": "Observed commit",
                    "problem": "UNKNOWN_NOT_RECORDED_IN_COMMIT_METADATA",
                    "solution": "Observed commit",
                    "evidence_refs": ["git_commit:abc"],
                    "novelty_observed": False,
                    "audience_relevance_observed": False,
                    "demonstration_available": False,
                    "commercial_relevance_observed": False,
                }
            ]
        },
    )

    result = build_media_os_runtime(tmp_path)

    assert result["real_evidence_present"] is True
    assert result["idea_backlog"]["candidate_count"] == 2
    assert result["idea_backlog"]["commercial_quant_available_count"] == 1
    assert result["idea_backlog"]["scored_candidate_count"] == 0
    assert {
        row["idea_id"]
        for row in result["idea_backlog"]["candidates"]
    } == {"manual:1", "empire:1"}

    empire = next(
        row
        for row in result["idea_backlog"]["candidates"]
        if row["idea_id"] == "empire:1"
    )
    assert empire["quant_packet_status"] == "AVAILABLE"
    assert empire["commercial_quant_is_media_score"] is False

    assert result["build_journal"]["entry_count"] == 1
    assert (
        result["build_journal"]["opportunity_candidate_count"]
        == 0
    )
    assert result["public_publish_authorized"] is False
    assert result["execution_authority"] == "none"


def test_runtime_surfaces_research_pack_claim_verification_gate(tmp_path):
    write_json(
        tmp_path,
        "runtime/media_os/input/research_pack_candidates.json",
        {
            "candidates": [
                {
                    "research_id": "media-research:1",
                    "topic": "Search Visibility",
                    "claims": [],
                    "sources": [
                        {
                            "source_ref": "source:1",
                            "source_type": "public_search_result",
                        }
                    ],
                    "verified_claim_count": 0,
                    "claim_verification_required": True,
                    "script_ready": False,
                    "execution_authority": "none",
                }
            ]
        },
    )

    result = build_media_os_runtime(tmp_path)

    research = result["research_packs"]
    assert research["candidate_count"] == 1
    assert research["verified_claim_count"] == 0
    assert research["script_ready_count"] == 0
    assert research["claim_verification_required_count"] == 1
    assert result["ready_for_claim_verification"] is True
    assert result["ready_for_script_generation"] is False
    assert result["public_publish_authorized"] is False
    assert result["execution_authority"] == "none"


def test_runtime_promotes_verified_research_into_content_pipeline_counts(tmp_path):
    write_json(
        tmp_path,
        "runtime/media_os/input/research_pack_candidates.json",
        {
            "candidates": [
                {
                    "research_id": "research:1",
                    "topic": "Automation Ops",
                    "claims": [],
                    "verified_claim_count": 0,
                    "claim_verification_required": True,
                    "script_ready": False,
                }
            ]
        },
    )
    write_json(
        tmp_path,
        "runtime/media_os/input/verified_research_packs.json",
        {
            "candidates": [
                {
                    "research_id": "research:1",
                    "topic": "Automation Ops",
                    "claims": [
                        {
                            "claim_id": "claim:1",
                            "text": "Observed supported claim.",
                            "evidence_refs": ["source:1"],
                            "verification": {
                                "verdict": "SUPPORTED",
                            },
                        }
                    ],
                    "verified_claim_count": 1,
                    "claim_verification_required": False,
                    "claim_verification_complete": True,
                    "script_ready": True,
                    "source_input_fingerprint": "abc",
                }
            ]
        },
    )
    write_json(
        tmp_path,
        "runtime/media_os/input/canonical_content_candidates.json",
        {
            "candidates": [
                {
                    "content_id": "content:1",
                    "topic": "Automation Ops",
                }
            ]
        },
    )
    write_json(
        tmp_path,
        "runtime/media_os/input/script_brief_candidates.json",
        {
            "candidates": [
                {
                    "content_id": "content:1",
                    "content_ref": "content:1",
                    "script_format": "tutorial",
                }
            ]
        },
    )

    result = build_media_os_runtime(tmp_path)

    research = result["research_packs"]
    pipeline = result["content_pipeline"]

    assert research["candidate_count"] == 1
    assert research["verified_pack_count"] == 1
    assert research["verified_claim_count"] == 1
    assert research["script_ready_count"] == 1
    assert research["claim_verification_required_count"] == 0

    assert pipeline["canonical_content_candidate_count"] == 1
    assert pipeline["script_brief_candidate_count"] == 1
    assert pipeline["script_prose_generated"] is False

    assert result["ready_for_claim_verification"] is False
    assert result["ready_for_script_generation"] is True
    assert result["ready_for_script_prose_generation"] is True
    assert result["ready_for_storyboard_generation"] is False
    assert result["public_publish_authorized"] is False
    assert result["execution_authority"] == "none"
