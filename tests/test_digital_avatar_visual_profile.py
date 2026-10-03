import pytest

from empire_os.digital_avatar_visual_profile import (
    AvatarVisualProfile,
    build_avatar_visual_render_plan,
)
from empire_os.digital_avatar_voice_sidecar import AvatarVoiceRenderArtifact


def audio(**overrides):
    values = {
        "render_id": "avatar-voice:render-1",
        "engine": "cosyvoice3",
        "voice_id": "phil-v1",
        "text_sha256": "text-hash-1",
        "audio_sha256": "audio-hash-1",
        "pcm_bytes": 48000,
        "sample_rate": 24000,
        "chunk_count": 12,
    }
    values.update(overrides)
    return AvatarVoiceRenderArtifact(**values)


def profile(**overrides):
    values = {
        "profile_ref": "visual:phil:v1",
        "owner_consent_evidence_ref": "consent:phil:visual-clone:v1",
        "source_image_ref": "visual-media:phil:portrait:v1",
        "engine_avatar_id": "phil-visual-v1",
        "preferred_engine": "ditto",
        "fallback_engines": ("musetalk15", "liveportrait"),
        "likeness_required": True,
        "expressive_motion_required": True,
        "commercial_use_required": True,
        "target_fps": 30,
    }
    values.update(overrides)
    return AvatarVisualProfile(**values)


def test_ditto_is_primary_realtime_commercial_visual_plan():
    plan = build_avatar_visual_render_plan(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        audio=audio(),
        profile=profile(),
        available_engines={
            "ditto": True,
            "musetalk15": True,
            "liveportrait": True,
        },
    )
    assert plan.engine == "ditto"
    assert plan.model_ref == "antgroup/ditto-talkinghead"
    assert plan.expressive_head_motion is True
    assert plan.commercial_ready is True
    assert plan.audio_sha256 == "audio-hash-1"
    assert plan.local_render_allowed is True
    assert plan.meeting_transmission_allowed is False
    assert plan.visual_execution_allowed is False
    assert plan.execution_authority == "none"


def test_lip_sync_only_fallback_is_rejected_when_expression_required():
    with pytest.raises(ValueError, match="no compliant realtime visual engine"):
        build_avatar_visual_render_plan(
            meeting_id="meeting-001",
            avatar_id="avatar-phil-v1",
            audio=audio(),
            profile=profile(preferred_engine="musetalk15", fallback_engines=()),
            available_engines={"musetalk15": True},
        )


def test_musetalk_can_be_fallback_when_expression_requirement_is_relaxed():
    plan = build_avatar_visual_render_plan(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        audio=audio(),
        profile=profile(
            preferred_engine="musetalk15",
            fallback_engines=(),
            expressive_motion_required=False,
        ),
        available_engines={"musetalk15": True},
    )
    assert plan.engine == "musetalk15"
    assert plan.expressive_head_motion is False
    assert plan.commercial_ready is True


def test_liveportrait_is_not_selected_for_audio_driven_primary_render():
    with pytest.raises(ValueError, match="no compliant realtime visual engine"):
        build_avatar_visual_render_plan(
            meeting_id="meeting-001",
            avatar_id="avatar-phil-v1",
            audio=audio(),
            profile=profile(
                preferred_engine="liveportrait",
                fallback_engines=(),
            ),
            available_engines={"liveportrait": True},
            commercial_overrides={"liveportrait": True},
        )


def test_visual_render_rejects_already_transmitted_audio():
    with pytest.raises(ValueError, match="pre-transmission audio artifact"):
        build_avatar_visual_render_plan(
            meeting_id="meeting-001",
            avatar_id="avatar-phil-v1",
            audio=audio(meeting_transmission_performed=True),
            profile=profile(),
            available_engines={"ditto": True},
        )


@pytest.mark.parametrize("fps", [0, 19, 61, 100])
def test_visual_profile_fps_is_bounded(fps):
    with pytest.raises(ValueError, match="target fps"):
        build_avatar_visual_render_plan(
            meeting_id="meeting-001",
            avatar_id="avatar-phil-v1",
            audio=audio(),
            profile=profile(target_fps=fps),
            available_engines={"ditto": True},
        )
