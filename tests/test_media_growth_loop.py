import pytest

from empire_os.media_build_journal import (
    BuildJournalEntry,
    content_opportunity_from_build,
)
from empire_os.media_channel_spawning import (
    build_channel_spawn_candidate,
    channel_portfolio_policy,
)
from empire_os.media_comment_intelligence import (
    MediaCommentObservation,
    classify_comment_signal,
    prepare_comment_reply_draft,
)
from empire_os.media_refresh import (
    build_content_refresh_candidate,
    detect_content_decay,
    kill_or_pivot_review,
)
from empire_os.media_repurposing import (
    build_repurposing_plan,
    content_fingerprint,
    duplication_guard,
)


def test_comment_intelligence_preserves_observation_without_invented_intent():
    comment = MediaCommentObservation(
        comment_id="comment-1",
        channel_id="empire-ai",
        video_id="video-1",
        text="Can this connect to our CRM automatically?",
        evidence_ref="youtube:comment:1",
    )

    signal = classify_comment_signal(
        comment,
        explicit_categories=("question",),
        product_request=True,
        requested_follow_up=True,
    )

    assert signal["product_request_observed"] is True
    assert signal["requested_follow_up_observed"] is True
    assert signal["buying_intent_inferred"] is False
    assert signal["reply_publish_authorized"] is False

    reply = prepare_comment_reply_draft(
        comment_signal=signal,
        reply_text="Yes — here is how the current integration works.",
        policy_refs=("brand:reply-policy:v1",),
    )
    assert reply["generic_bot_reply_allowed"] is False
    assert reply["publish_authorized"] is False
    assert reply["publish_action_performed"] is False


def test_build_journal_generates_candidate_not_media_score():
    entry = BuildJournalEntry(
        entry_id="journal-1",
        system="Buyer Scout",
        change="Fixed runtime ownership regression",
        problem="systemd recreated root-owned runtime files",
        solution="run refresh services as ubuntu",
        evidence_refs=("commit:226f85cd", "test:runtime-worker"),
        lessons=("service identity is part of runtime correctness",),
    )

    result = content_opportunity_from_build(
        entry,
        novelty_observed=True,
        audience_relevance_observed=True,
        demonstration_available=True,
        commercial_relevance_observed=False,
    )

    assert result["state"] == "MEDIA_OPPORTUNITY_CANDIDATE"
    assert result["media_score_created"] is False
    assert result["ranking_owner"] == "quant_brain_and_opportunity_factory"
    assert result["public_publish_authorized"] is False


def test_repurposing_keeps_one_canonical_fact_source():
    plan = build_repurposing_plan(
        canonical_content_ref="content:1",
        derivative_types=(
            "youtube_long_form",
            "youtube_short",
            "linkedin",
            "blog",
        ),
        evidence_refs=("research:1",),
    )

    assert plan["derivative_count"] == 4
    assert plan["independent_fact_regeneration_allowed"] is False
    assert all(
        row["source_ref"] == "content:1"
        for row in plan["derivatives"]
    )
    assert plan["public_publish_authorized"] is False


def test_duplication_guard_detects_repeated_creative_language():
    fingerprint_a = content_fingerprint(
        topic="AI lead generation",
        thesis="Build an automated sales engine",
        hook="We built an AI sales engine",
    )
    fingerprint_b = content_fingerprint(
        topic="AI lead generation",
        thesis="Build an automated sales engine",
        hook="We built an AI sales engine",
    )
    assert fingerprint_a == fingerprint_b

    result = duplication_guard(
        candidate={
            "topic": "AI lead generation",
            "title": "We built an AI sales engine",
            "hook": "We built an AI sales engine",
            "thumbnail_text": "AI SALES ENGINE",
        },
        historical_items=[
            {
                "id": "old-1",
                "topic": "AI lead generation",
                "title": "We built an AI sales engine",
                "hook": "We built an AI sales engine",
                "thumbnail_text": "AI SALES ENGINE",
            }
        ],
    )
    assert result["duplicate_risk"] is True
    assert result["automatic_rejection"] is False


def test_decay_and_refresh_actions_are_evidence_candidates_only():
    decay = detect_content_decay(
        recent_values=(60, 58, 55),
        historical_values=(100, 105, 95),
    )
    assert decay["structural_decay_detected"] is True
    assert decay["causal_explanation_created"] is False

    refresh = build_content_refresh_candidate(
        video_id="video-1",
        evidence_refs=("analytics:video-1",),
        historical_value_observed=True,
        falling_ctr_observed=True,
        outdated_fact_observed=False,
        product_version_changed=False,
        old_thumbnail_observed=True,
        search_demand_changed=False,
    )
    assert refresh["refresh_candidate"] is True
    assert "thumbnail_test_candidate" in refresh["candidate_actions"]
    assert refresh["automatic_public_mutation"] is False


def test_kill_pivot_review_avoids_sunk_cost_automation():
    result = kill_or_pivot_review(
        series_id="series-1",
        observed_episode_count=6,
        repeated_underperformance=True,
        audience_mismatch_observed=True,
        production_cost_disproportionate=False,
        strategic_relevance_lost=False,
        evidence_refs=("analytics:series-1",),
    )
    assert result["decision"] == "PIVOT_OR_RETIRE_CANDIDATE"
    assert result["automatic_series_shutdown"] is False


def test_channel_spawning_requires_depth_and_founder_review():
    ideas = [
        {
            "idea_id": f"idea-{index}",
            "topic": f"Roofing AI topic {index}",
        }
        for index in range(35)
    ]
    result = build_channel_spawn_candidate(
        channel_concept="AI for Roofing",
        credible_ideas=ideas,
        evidence_refs=("search:roofing", "youtube:roofing"),
        dimension_evidence={
            "audience_demand": 0.8,
            "content_supply_gap": 0.6,
            "trend_velocity": 0.7,
            "empire_expertise": 0.9,
            "content_depth": 1.0,
            "product_alignment": 0.9,
        },
    )

    assert result["credible_idea_count"] == 35
    assert result["score"] is None
    assert result["ranking_owner"] == "quant_brain"
    assert result["launch_gate"]["decision"] == (
        "FOUNDER_REVIEW_CANDIDATE"
    )
    assert result["channel_created"] is False
    assert result["channel_launch_authorized"] is False
    assert result["execution_authority"] == "founder_gate"


def test_channel_portfolio_forbids_mass_launch():
    policy = channel_portfolio_policy()
    assert policy["flagship_channel"] == "EMPIRE AI"
    assert policy["flagship_first"] is True
    assert policy["simultaneous_mass_channel_launch"] is False
    assert policy["new_channel_launch_authorized"] is False
