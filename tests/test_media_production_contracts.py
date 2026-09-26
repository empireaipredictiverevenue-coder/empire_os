import pytest

from empire_os.media_creative_package import (
    ThumbnailConcept,
    TitleCandidate,
    shortlist_creative_pairs,
    title_thumbnail_pair,
)
from empire_os.media_quality_gate import (
    MediaQCCheck,
    evaluate_media_quality_gate,
)
from empire_os.media_renderer import (
    MediaRenderJob,
    build_render_plan,
    cost_governor,
    queue_policy,
)
from empire_os.media_rights_provenance import (
    MediaAssetProvenance,
    build_rights_manifest,
    synthetic_media_disclosure,
)
from empire_os.media_timeline import (
    MediaShot,
    build_media_timeline,
    timeline_asset_plan,
)


def test_title_thumbnail_pair_penalizes_message_duplication_signal():
    title = TitleCandidate(
        candidate_id="title-1",
        text="We Built an AI Sales Engine",
        mode="browse_led",
        evidence_refs=("content:1",),
        evaluator_scores={
            "clarity": 0.9,
            "curiosity": 0.8,
        },
    )
    thumb = ThumbnailConcept(
        concept_id="thumb-1",
        visual_question="Can AI actually replace the repetitive work?",
        subject="EmpireOS dashboard",
        composition="dashboard left, strong subject right",
        thumbnail_text="AI SALES ENGINE",
        evidence_refs=("content:1",),
        rights_refs=("asset:rights:1",),
        evaluator_scores={
            "clarity": 0.9,
            "mobile_readability": 0.9,
        },
    )

    pair = title_thumbnail_pair(title, thumb)

    assert pair["classification"] == "CREATIVE_HEURISTIC"
    assert pair["experiment_required_for_causal_claim"] is True
    assert pair["public_publish_authorized"] is False
    assert pair["execution_authority"] == "none"

    shortlist = shortlist_creative_pairs([pair], limit=3)
    assert shortlist["shortlist_count"] == 1
    assert shortlist["winner_declared"] is False
    assert shortlist["experiment_required"] is True


def test_timeline_requires_provenance_for_evidence_visuals():
    with pytest.raises(ValueError, match="provenance"):
        MediaShot(
            scene_id="scene-1",
            duration_seconds=6,
            narration="Here is the observed trend.",
            visual_intent="show observed growth",
            asset_type="chart",
        ).as_dict()

    timeline = build_media_timeline(
        video_id="video-1",
        script_ref="script:1",
        research_ref="research:1",
        brand_profile_ref="brand:empire-ai",
        shots=(
            MediaShot(
                scene_id="scene-1",
                duration_seconds=6,
                narration="Here is the observed trend.",
                visual_intent="show observed growth",
                asset_type="chart",
                data_refs=("evidence:trend:1",),
                provenance_refs=("source:trend:1",),
            ),
            MediaShot(
                scene_id="scene-2",
                duration_seconds=4,
                narration="This is what we built.",
                visual_intent="real Empire product footage",
                asset_type="product_demo",
                provenance_refs=("asset:owned:screen-1",),
            ),
        ),
    )

    assert timeline["shot_count"] == 2
    assert timeline["duration_seconds"] == 10.0
    assert timeline["shots"][1]["start_seconds"] == 6.0
    assert timeline["public_publish_authorized"] is False

    assets = timeline_asset_plan(timeline)
    assert assets["asset_count"] == 2
    assert assets["generation_authorized"] is False
    assert assets["rights_review_required"] is True


def test_rights_manifest_fails_closed_for_unknown_or_missing_attribution():
    owned = MediaAssetProvenance(
        asset_id="owned-1",
        asset_type="screen_recording",
        source_type="empire_owned",
        source_ref="asset:screen-1",
        rights_state="OWNED",
    )
    unknown = MediaAssetProvenance(
        asset_id="unknown-1",
        asset_type="b_roll",
        source_type="external",
        source_ref="https://example.test/video",
        rights_state="UNKNOWN",
    )

    manifest = build_rights_manifest(
        production_id="prod-1",
        assets=[owned, unknown],
    )

    assert manifest["commercial_release_ready"] is False
    assert manifest["blocked_asset_ids"] == ["unknown-1"]
    assert manifest["public_publish_authorized"] is False

    disclosure = synthetic_media_disclosure(
        synthetic_event_or_place=True,
    )
    assert disclosure["platform_disclosure_review_required"] is True
    assert disclosure["present_as_unaltered_real_event_authorized"] is False


def test_quality_gate_requires_rights_and_no_required_unknowns():
    rights = build_rights_manifest(
        production_id="prod-ready",
        assets=[
            MediaAssetProvenance(
                asset_id="owned",
                asset_type="logo",
                source_type="empire_owned",
                source_ref="brand:logo",
                rights_state="OWNED",
            )
        ],
    )
    checks = [
        MediaQCCheck(
            category="video",
            check="resolution",
            status="PASS",
            evidence_refs=("ffprobe:1",),
        ),
        MediaQCCheck(
            category="content",
            check="facts",
            status="PASS",
            evidence_refs=("research:1",),
        ),
    ]

    gate = evaluate_media_quality_gate(
        checks,
        rights_manifest=rights,
    )

    assert gate["decision"] == "QC_READY_FOR_GOVERNED_PUBLISH_REVIEW"
    assert gate["publish_ready_candidate"] is True
    assert gate["public_publish_authorized"] is False

    blocked = evaluate_media_quality_gate(
        [
            *checks,
            MediaQCCheck(
                category="audio",
                check="loudness",
                status="UNKNOWN",
            ),
        ],
        rights_manifest=rights,
    )
    assert blocked["decision"] == "HOLD_FOR_EVIDENCE"
    assert blocked["publish_ready_candidate"] is False


def test_render_plan_requires_verified_ffmpeg_profile_and_gates_spend():
    job = MediaRenderJob(
        job_id="render-1",
        production_id="prod-1",
        timeline_ref="timeline:1",
        output_profile="youtube_4k",
        priority="P1",
        renderer="ffmpeg",
        estimated_cost_usd=4.0,
    )

    blocked = build_render_plan(job)
    assert blocked["state"] == "BLOCKED_LICENSE_PROFILE"
    assert blocked["render_executed"] is False

    ready = build_render_plan(
        job,
        ffmpeg_build_ref="ffmpeg:build:verified",
        codec_policy_ref="codec:policy:verified",
    )
    assert ready["state"] == "INTERNAL_RENDER_CANDIDATE"
    assert ready["render_executed"] is False
    assert ready["execution_authority"] == "none"

    expensive = build_render_plan(
        MediaRenderJob(
            job_id="render-2",
            production_id="prod-2",
            timeline_ref="timeline:2",
            output_profile="flagship_4k",
            priority="P1",
            renderer="ffmpeg",
            estimated_cost_usd=100.0,
        ),
        ffmpeg_build_ref="ffmpeg:build:verified",
        codec_policy_ref="codec:policy:verified",
        material_spend_threshold_usd=50.0,
    )
    assert expensive["state"] == "FOUNDER_GATE_MATERIAL_SPEND"
    assert expensive["founder_gate_required"] is True
    assert expensive["execution_authority"] == "founder_gate"


def test_render_queue_and_cost_governor_do_not_spend():
    policy = queue_policy()
    assert policy["live_queue_enabled"] is False
    assert policy["automatic_gpu_provisioning"] is False
    assert policy["material_spend_authorized"] is False

    decision = cost_governor(
        opportunity_score=0.9,
        expected_cost_usd=12,
        expected_gpu_minutes=8,
        premium_generation_requested=True,
    )
    assert decision["route"] == "PREMIUM_GENERATION_CANDIDATE"
    assert decision["automatic_spend_authorized"] is False
    assert decision["actual_cost_usd"] is None
    assert decision["actual_revenue"] is False
