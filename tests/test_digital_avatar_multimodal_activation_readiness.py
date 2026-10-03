from dataclasses import replace

import pytest

from empire_os.digital_avatar import DigitalAvatarIdentity
from empire_os.digital_avatar_fleet import AvatarFleetRuntimeBinding
from empire_os.digital_avatar_fleet_media_binding import bind_avatar_fleet_media
from empire_os.digital_avatar_multimodal_activation_readiness import (
    assess_multimodal_activation_readiness,
)
from empire_os.digital_avatar_visual_profile import (
    AvatarVisualEngineCapability,
)
from empire_os.digital_avatar_visual_registry import AvatarVisualRegistration
from empire_os.digital_avatar_voice_profile import AvatarVoiceEngineCapability
from empire_os.digital_avatar_voice_registry import AvatarVoiceRegistration


def runtime():
    return AvatarFleetRuntimeBinding(
        tenant_id="tenant-a",
        avatar_id="avatar-a",
        owner_ref="person:a",
        owner_name="Owner A",
        capability_labels=("sales",),
        membership_user_id="user-1",
        membership_role="operator",
        owner_consent_evidence_ref="consent:owner:a",
    )


def identity(*, voice=True, visual=True):
    return DigitalAvatarIdentity(
        avatar_id="avatar-a",
        owner_name="Owner A",
        display_name="Owner A — AI Digital Avatar",
        organisation_name="Empire AI",
        disclosure_text="I am Owner A's authorised AI Digital Avatar.",
        owner_consent_evidence_ref="consent:owner:a",
        voice_profile_ref="voice:a:v1" if voice else None,
        visual_profile_ref="visual:a:v1" if visual else None,
    )


def voice_registration(engine="cosyvoice3"):
    return AvatarVoiceRegistration(
        profile_ref="voice:a:v1",
        avatar_id="avatar-a",
        owner_consent_evidence_ref="consent:owner:a",
        voice_consent_evidence_ref="consent:voice:a",
        preferred_engine=engine,
        engine_voice_id="voice-engine-a",
        reference_audio_ref="private:audio:a",
        reference_transcript_ref="private:transcript:a",
        language="en-GB",
        profile_sha256="a" * 64,
    )


def visual_registration(engine="ditto"):
    return AvatarVisualRegistration(
        profile_ref="visual:a:v1",
        avatar_id="avatar-a",
        owner_consent_evidence_ref="consent:owner:a",
        visual_consent_evidence_ref="consent:visual:a",
        preferred_engine=engine,
        engine_avatar_id="visual-engine-a",
        source_image_ref="private:image:a",
        target_fps=30,
        profile_sha256="b" * 64,
    )


def binding(*, voice=True, visual=True, voice_engine="cosyvoice3", visual_engine="ditto"):
    return bind_avatar_fleet_media(
        runtime=runtime(),
        identity=identity(voice=voice, visual=visual),
        voice_registration=(
            voice_registration(voice_engine)
            if voice else None
        ),
        visual_registration=(
            visual_registration(visual_engine)
            if visual else None
        ),
    )


def assess(value, required, **overrides):
    params = {
        "binding": value,
        "meeting_id": "meeting-001",
        "required_media": required,
        "available_voice_engines": {"cosyvoice3": True},
        "available_visual_engines": {"ditto": True},
    }
    params.update(overrides)
    return assess_multimodal_activation_readiness(**params)


def test_voice_only_ready_with_compliant_available_clone_engine():
    result = assess(binding(visual=False), "voice")
    assert result.activation_ready is True
    assert result.voice_ready is True
    assert result.visual_ready is False
    assert result.blockers == ()


def test_visual_only_ready_with_compliant_available_commercial_engine():
    result = assess(binding(voice=False), "visual")
    assert result.activation_ready is True
    assert result.voice_ready is False
    assert result.visual_ready is True
    assert result.blockers == ()


def test_multimodal_requires_both_media_paths():
    ready = assess(binding(), "multimodal")
    assert ready.activation_ready is True
    assert ready.voice_ready is True
    assert ready.visual_ready is True

    blocked = assess(
        binding(visual=False),
        "multimodal",
    )
    assert blocked.activation_ready is False
    assert "visual_media_binding_missing" in blocked.blockers


def test_unavailable_required_engine_blocks_activation():
    result = assess(
        binding(),
        "voice",
        available_voice_engines={"cosyvoice3": False},
    )
    assert result.activation_ready is False
    assert result.blockers == ("voice_engine_unavailable",)


def test_generic_non_clone_voice_engine_blocks_clone_activation():
    generic = AvatarVoiceEngineCapability(
        engine="generic",
        zero_shot_clone=False,
        streaming=True,
        local_self_hosted=True,
        license_id="Apache-2.0",
        model_ref="generic:test",
    )
    value = binding(visual=False, voice_engine="generic")
    result = assess(
        value,
        "voice",
        voice_capabilities={"generic": generic},
        available_voice_engines={"generic": True},
    )
    assert result.activation_ready is False
    assert "voice_engine_not_clone_capable" in result.blockers


def test_noncommercial_or_non_audio_driven_visual_engine_blocks():
    unsafe = AvatarVisualEngineCapability(
        engine="unsafe",
        audio_driven=False,
        realtime=True,
        expressive_head_motion=True,
        local_self_hosted=True,
        code_license_id="test",
        model_commercial_use=False,
        commercial_ready_by_default=False,
        model_ref="unsafe:test",
    )
    value = binding(voice=False, visual_engine="unsafe")
    result = assess(
        value,
        "visual",
        visual_capabilities={"unsafe": unsafe},
        available_visual_engines={"unsafe": True},
    )
    assert result.activation_ready is False
    assert "visual_engine_not_audio_driven" in result.blockers
    assert "visual_engine_not_commercial_ready" in result.blockers


def test_explicit_visual_commercial_override_still_requires_model_commercial_use():
    engine = AvatarVisualEngineCapability(
        engine="reviewed",
        audio_driven=True,
        realtime=True,
        expressive_head_motion=True,
        local_self_hosted=True,
        code_license_id="test",
        model_commercial_use=False,
        commercial_ready_by_default=False,
        model_ref="reviewed:test",
    )
    value = binding(voice=False, visual_engine="reviewed")
    result = assess(
        value,
        "visual",
        visual_capabilities={"reviewed": engine},
        available_visual_engines={"reviewed": True},
        visual_commercial_overrides={"reviewed": True},
    )
    assert result.activation_ready is False
    assert result.blockers == ("visual_engine_not_commercial_ready",)


def test_binding_authority_invariant_fails_before_readiness():
    value = binding(visual=False)
    with pytest.raises(ValueError, match="forbidden authority"):
        assess(
            replace(value, speech_execution_allowed=True),
            "voice",
        )


def test_readiness_never_grants_render_provider_or_execution_authority():
    result = assess(binding(), "multimodal")
    assert result.media_identity_verified is True
    assert result.recommendation_only is True
    assert result.render_execution is False
    assert result.provider_call_performed is False
    assert result.meeting_join_performed is False
    assert result.output_media_start_performed is False
    assert result.speech_execution_allowed is False
    assert result.visual_execution_allowed is False
    assert result.commercial_execution_allowed is False
    assert result.payment_execution_allowed is False
    assert result.revenue_recognition_allowed is False
    assert result.execution_authority == "none"


def test_unknown_media_requirement_fails_closed():
    with pytest.raises(ValueError, match="unsupported"):
        assess(binding(), "hologram")
