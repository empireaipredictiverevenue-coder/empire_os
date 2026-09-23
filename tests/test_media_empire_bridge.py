from pathlib import Path
from types import SimpleNamespace

import empire_os.media_empire_bridge as module
from empire_os.media_empire_bridge import (
    build_media_ideas_from_opportunity_radar,
    collect_git_build_journal,
    refresh_media_empire_bridge,
)


def radar_payload():
    return {
        "schema_version": "empire.predictive_cloud.opportunity_radar.v1",
        "mode": "OBSERVE",
        "candidates": [
            {
                "opportunity_key": "community_pain:search_visibility",
                "opportunity_class": "community_pain",
                "source": "community_intent",
                "title": "Search Visibility",
                "niche": None,
                "trigger": "observed_public_pain",
                "observed_priority_score": 65,
                "evidence_strength": "moderate",
                "evidence_refs": [
                    "https://example.test/public-observation"
                ],
                "offer_key": "search_growth_command",
                "products": ["geo_ai_visibility"],
                "recommended_next_actions": [
                    "collect_serp_evidence"
                ],
                "commercial_demand_observed": False,
                "buyer_intent_inferred": False,
                "revenue_inferred": False,
                "execution_authority": "none",
            }
        ],
        "execution_authority": "none",
    }


def quant_payload(status="AVAILABLE"):
    return {
        "schema_version": "empire.opportunity_quant_review.v1",
        "mode": "OBSERVE",
        "items": [
            {
                "opportunity_key": "community_pain:search_visibility",
                "decision_packet": {
                    "schema_version": "empire.quant.decision_packet.v1",
                    "candidate_id": "community_pain:search_visibility",
                    "status": status,
                    "prediction_only": True,
                    "actual_revenue": False,
                    "recommendation_only": True,
                    "execution_authority": "none",
                },
            }
        ],
        "execution_authority": "none",
    }


def test_opportunity_radar_becomes_media_candidate_without_fake_media_score():
    result = build_media_ideas_from_opportunity_radar(
        radar_payload(),
        quant_review=quant_payload(),
    )

    assert result["candidate_count"] == 1
    assert result["commercial_quant_available_count"] == 1
    assert result["media_score_created"] is False

    row = result["candidates"][0]
    assert row["topic"] == "Search Visibility"
    assert row["source_systems"] == [
        "opportunity_radar",
        "community_intent",
    ]
    assert row["product_refs"] == ["geo_ai_visibility"]
    assert row["opportunity_refs"] == [
        "community_pain:search_visibility"
    ]
    assert row["opportunity_features"] == {}
    assert row["quant_packet_status"] == "AVAILABLE"
    assert row["commercial_quant_is_media_score"] is False
    assert (
        row["source_context"]["observed_priority_score"]
        == 65
    )
    assert row["automatic_build_authorized"] is False
    assert row["public_publish_authorized"] is False
    assert row["execution_authority"] == "none"


def test_missing_opportunity_evidence_is_rejected_not_invented():
    radar = radar_payload()
    radar["candidates"][0]["evidence_refs"] = []

    result = build_media_ideas_from_opportunity_radar(radar)

    assert result["candidate_count"] == 0
    assert result["rejected_count"] == 1
    assert result["media_score_created"] is False


def test_git_build_journal_marks_unknown_problem_and_infers_no_content_flags(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            stdout=(
                "abc123\x1f2026-09-23T12:00:00+00:00"
                "\x1fAdd Media OS bridge\n"
            )
        ),
    )

    result = collect_git_build_journal(tmp_path, limit=30)

    assert result["git_available"] is True
    assert result["entry_count"] == 1
    row = result["items"][0]

    assert row["entry_id"] == "git:abc123"
    assert row["change"] == "Add Media OS bridge"
    assert row["problem"] == "UNKNOWN_NOT_RECORDED_IN_COMMIT_METADATA"
    assert row["evidence_refs"] == ["git_commit:abc123"]
    assert row["novelty_observed"] is False
    assert row["audience_relevance_observed"] is False
    assert row["demonstration_available"] is False
    assert row["commercial_relevance_observed"] is False
    assert result["content_opportunity_flags_inferred"] is False


def test_bridge_writes_separate_empire_inputs_without_external_action(
    monkeypatch,
    tmp_path,
):
    opportunity = (
        tmp_path / "runtime/opportunity_radar/latest.json"
    )
    opportunity.parent.mkdir(parents=True)
    opportunity.write_text(__import__("json").dumps(radar_payload()))

    quant = (
        tmp_path
        / "runtime/opportunity_factory/quant_review_latest.json"
    )
    quant.parent.mkdir(parents=True)
    quant.write_text(__import__("json").dumps(quant_payload()))

    monkeypatch.setattr(
        module,
        "collect_git_build_journal",
        lambda *_args, **_kwargs: {
            "schema_version": "empire.media.git_build_journal.v1",
            "mode": "OBSERVE",
            "git_available": True,
            "entry_count": 1,
            "items": [
                {
                    "entry_id": "git:abc",
                    "system": "EmpireOS",
                    "change": "Observed change",
                    "problem": "UNKNOWN_NOT_RECORDED_IN_COMMIT_METADATA",
                    "solution": "Observed change",
                    "evidence_refs": ["git_commit:abc"],
                    "before_refs": [],
                    "after_refs": ["git_commit:abc"],
                    "screenshot_refs": [],
                    "metric_refs": [],
                    "business_relevance": None,
                    "lessons": [],
                    "created_at": "2026-09-23T12:00:00+00:00",
                    "novelty_observed": False,
                    "audience_relevance_observed": False,
                    "demonstration_available": False,
                    "commercial_relevance_observed": False,
                }
            ],
            "content_opportunity_flags_inferred": False,
            "public_publish_authorized": False,
            "execution_authority": "none",
        },
    )

    result = refresh_media_empire_bridge(tmp_path)

    assert result["opportunity_radar_available"] is True
    assert result["quant_review_available"] is True
    assert result["media_idea_candidate_count"] == 1
    assert result["commercial_quant_available_count"] == 1
    assert result["git_build_journal_entry_count"] == 1
    assert result["external_action_performed"] is False
    assert result["database_write_performed"] is False
    assert result["media_score_created"] is False
    assert result["actual_revenue"] is False
    assert result["execution_authority"] == "none"

    assert (
        tmp_path
        / "runtime/media_os/input/empire_opportunity_ideas.json"
    ).exists()
    assert (
        tmp_path
        / "runtime/media_os/input/empire_build_journal.json"
    ).exists()
