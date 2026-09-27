import pytest

from empire_os.video_studio_v1 import VideoScene, build_video_studio_plan


def test_hybrid_video_plan_uses_real_proof_plus_generated_broll():
    result = build_video_studio_plan(
        title="Austin roofing opportunity demo",
        niche="roofing",
        output_type="sales_demo",
        scenes=[
            VideoScene(
                scene_type="live_capture",
                purpose="Show live opportunity map",
                evidence_ref="opportunity:austin:1",
                source_asset_ref="screen:opportunities",
                duration_seconds=20,
            ),
            VideoScene(
                scene_type="screenshot_motion",
                purpose="Animate the qualification result",
                evidence_ref="omega:lead:1",
                source_asset_ref="screenshot:omega:1",
                duration_seconds=12,
            ),
            VideoScene(
                scene_type="ai_broll",
                purpose="Bridge into contractor workflow",
                evidence_ref=None,
                prompt="Commercial roofing operations, cinematic neutral b-roll",
                duration_seconds=8,
            ),
            VideoScene(
                scene_type="cta",
                purpose="Invite buyer to review a pilot",
                evidence_ref=None,
                duration_seconds=6,
            ),
        ],
    )

    assert result["generation"]["social_cuts"] is True
    assert result["telemetry"]["cta_click"] is True
    assert result["telemetry"]["conversion_intelligence_handoff"] is True
    assert result["truth_policy"]["generated_broll_is_proof"] is False
    assert result["truth_policy"]["synthetic_metrics_allowed"] is False
    assert result["generation_enabled"] is False
    assert result["publishing_enabled"] is False


def test_ai_broll_requires_prompt():
    with pytest.raises(ValueError, match="prompt"):
        build_video_studio_plan(
            title="bad",
            niche="roofing",
            output_type="social_cut",
            scenes=[
                VideoScene(
                    scene_type="ai_broll",
                    purpose="bad scene",
                    evidence_ref=None,
                )
            ],
        )


def test_proof_scene_requires_evidence():
    with pytest.raises(ValueError, match="evidence_ref"):
        build_video_studio_plan(
            title="bad proof",
            niche="roofing",
            output_type="sales_demo",
            scenes=[
                VideoScene(
                    scene_type="live_capture",
                    purpose="claim proof",
                    evidence_ref=None,
                )
            ],
        )
