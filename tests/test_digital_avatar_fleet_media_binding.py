from dataclasses import replace

import pytest

from empire_os.digital_avatar import DigitalAvatarIdentity
from empire_os.digital_avatar_fleet import AvatarFleetRuntimeBinding
from empire_os.digital_avatar_fleet_media_binding import (
    bind_avatar_fleet_media,
    normalize_avatar_fleet_media_bindings,
)
from empire_os.digital_avatar_visual_registry import AvatarVisualRegistration
from empire_os.digital_avatar_voice_registry import AvatarVoiceRegistration


def runtime(**overrides):
    values = {
        "tenant_id": "tenant-a",
        "avatar_id": "avatar-a",
        "owner_ref": "person:a",
        "owner_name": "Owner A",
        "capability_labels": ("sales",),
        "membership_user_id": "user-1",
        "membership_role": "operator",
        "owner_consent_evidence_ref": "consent:owner:a",
    }
    values.update(overrides)
    return AvatarFleetRuntimeBinding(**values)


def identity(*, voice=True, visual=True, **overrides):
    values = {
        "avatar_id": "avatar-a",
        "owner_name": "Owner A",
        "display_name": "Owner A — AI Digital Avatar",
        "organisation_name": "Empire AI",
        "disclosure_text": "I am Owner A's authorised AI Digital Avatar.",
        "owner_consent_evidence_ref": "consent:owner:a",
        "voice_profile_ref": "voice:a:v1" if voice else None,
        "visual_profile_ref": "visual:a:v1" if visual else None,
    }
    values.update(overrides)
    return DigitalAvatarIdentity(**values)


def voice_registration(**overrides):
    values = {
        "profile_ref": "voice:a:v1",
        "avatar_id": "avatar-a",
        "owner_consent_evidence_ref": "consent:owner:a",
        "voice_consent_evidence_ref": "consent:voice:a",
        "preferred_engine": "empire_voice",
        "engine_voice_id": "voice-engine-a",
        "reference_audio_ref": "private:audio:a",
        "reference_transcript_ref": "private:transcript:a",
        "language": "en-GB",
        "profile_sha256": "a" * 64,
    }
    values.update(overrides)
    return AvatarVoiceRegistration(**values)


def visual_registration(**overrides):
    values = {
        "profile_ref": "visual:a:v1",
        "avatar_id": "avatar-a",
        "owner_consent_evidence_ref": "consent:owner:a",
        "visual_consent_evidence_ref": "consent:visual:a",
        "preferred_engine": "empire_visual",
        "engine_avatar_id": "visual-engine-a",
        "source_image_ref": "private:image:a",
        "target_fps": 30,
        "profile_sha256": "b" * 64,
    }
    values.update(overrides)
    return AvatarVisualRegistration(**values)


def test_voice_only_binding_is_valid_and_redacted():
    value = bind_avatar_fleet_media(
        runtime=runtime(),
        identity=identity(visual=False),
        voice_registration=voice_registration(),
    )
    assert value.voice_consent_verified is True
    assert value.visual_profile_ref is None
    rendered = repr(value.as_dict())
    assert "private:audio:a" not in rendered
    assert "private:transcript:a" not in rendered
    assert value.raw_reference_media_included is False
    assert value.execution_authority == "none"


def test_visual_only_binding_is_valid_and_redacted():
    value = bind_avatar_fleet_media(
        runtime=runtime(),
        identity=identity(voice=False),
        visual_registration=visual_registration(),
    )
    assert value.visual_consent_verified is True
    assert value.voice_profile_ref is None
    assert "private:image:a" not in repr(value.as_dict())


def test_voice_and_visual_binding_is_valid():
    value = bind_avatar_fleet_media(
        runtime=runtime(),
        identity=identity(),
        voice_registration=voice_registration(),
        visual_registration=visual_registration(),
    )
    assert value.voice_profile_ref == "voice:a:v1"
    assert value.visual_profile_ref == "visual:a:v1"
    assert value.voice_profile_sha256 == "a" * 64
    assert value.visual_profile_sha256 == "b" * 64
    assert value.speech_execution_allowed is False
    assert value.visual_execution_allowed is False
    assert value.meeting_transmission_authority is False


def test_runtime_identity_avatar_or_consent_mismatch_fails_closed():
    with pytest.raises(PermissionError, match="avatar mismatch"):
        bind_avatar_fleet_media(
            runtime=runtime(avatar_id="avatar-b"),
            identity=identity(),
            voice_registration=voice_registration(),
            visual_registration=visual_registration(),
        )
    with pytest.raises(PermissionError, match="consent mismatch"):
        bind_avatar_fleet_media(
            runtime=runtime(owner_consent_evidence_ref="consent:other"),
            identity=identity(),
            voice_registration=voice_registration(),
            visual_registration=visual_registration(),
        )


def test_declared_profile_requires_matching_registration():
    with pytest.raises(ValueError, match="voice profile registration missing"):
        bind_avatar_fleet_media(
            runtime=runtime(),
            identity=identity(),
            visual_registration=visual_registration(),
        )
    with pytest.raises(ValueError, match="visual profile registration missing"):
        bind_avatar_fleet_media(
            runtime=runtime(),
            identity=identity(),
            voice_registration=voice_registration(),
        )


def test_profile_ref_mismatch_is_rejected():
    with pytest.raises(ValueError, match="voice profile ref mismatch"):
        bind_avatar_fleet_media(
            runtime=runtime(),
            identity=identity(visual=False),
            voice_registration=voice_registration(profile_ref="voice:wrong"),
        )


def test_registration_with_raw_media_or_transmission_authority_is_rejected():
    with pytest.raises(ValueError, match="raw-media invariant"):
        bind_avatar_fleet_media(
            runtime=runtime(),
            identity=identity(visual=False),
            voice_registration=voice_registration(raw_reference_media_stored=True),
        )
    with pytest.raises(ValueError, match="transmission authority forbidden"):
        bind_avatar_fleet_media(
            runtime=runtime(),
            identity=identity(voice=False),
            visual_registration=visual_registration(
                meeting_transmission_authority=True,
            ),
        )


def test_exact_duplicate_media_binding_is_idempotent():
    value = bind_avatar_fleet_media(
        runtime=runtime(),
        identity=identity(),
        voice_registration=voice_registration(),
        visual_registration=visual_registration(),
    )
    assert normalize_avatar_fleet_media_bindings((value, value)) == (value,)


def test_voice_profile_cannot_be_reused_by_another_avatar_or_tenant():
    first = bind_avatar_fleet_media(
        runtime=runtime(),
        identity=identity(visual=False),
        voice_registration=voice_registration(),
    )
    second = bind_avatar_fleet_media(
        runtime=runtime(
            avatar_id="avatar-b",
            owner_ref="person:b",
            owner_name="Owner B",
            owner_consent_evidence_ref="consent:owner:b",
        ),
        identity=identity(
            visual=False,
            avatar_id="avatar-b",
            owner_name="Owner B",
            owner_consent_evidence_ref="consent:owner:b",
            voice_profile_ref="voice:a:v1",
        ),
        voice_registration=voice_registration(
            avatar_id="avatar-b",
            owner_consent_evidence_ref="consent:owner:b",
            voice_consent_evidence_ref="consent:voice:b",
        ),
    )
    with pytest.raises(ValueError, match="voice_profile_reuse_conflict"):
        normalize_avatar_fleet_media_bindings((first, second))

    third = bind_avatar_fleet_media(
        runtime=runtime(tenant_id="tenant-b"),
        identity=identity(visual=False),
        voice_registration=voice_registration(),
    )
    with pytest.raises(ValueError, match="voice_profile_reuse_conflict"):
        normalize_avatar_fleet_media_bindings((first, third))


def test_engine_voice_id_cannot_be_reused_across_avatar_bindings():
    first = bind_avatar_fleet_media(
        runtime=runtime(),
        identity=identity(visual=False),
        voice_registration=voice_registration(),
    )
    second = bind_avatar_fleet_media(
        runtime=runtime(
            avatar_id="avatar-b",
            owner_ref="person:b",
            owner_name="Owner B",
            owner_consent_evidence_ref="consent:owner:b",
        ),
        identity=identity(
            visual=False,
            avatar_id="avatar-b",
            owner_name="Owner B",
            owner_consent_evidence_ref="consent:owner:b",
            voice_profile_ref="voice:b:v1",
        ),
        voice_registration=voice_registration(
            profile_ref="voice:b:v1",
            avatar_id="avatar-b",
            owner_consent_evidence_ref="consent:owner:b",
            voice_consent_evidence_ref="consent:voice:b",
            profile_sha256="c" * 64,
            engine_voice_id="voice-engine-a",
        ),
    )
    with pytest.raises(ValueError, match="voice_engine_reuse_conflict"):
        normalize_avatar_fleet_media_bindings((first, second))


def test_binding_key_is_deterministic_and_self_verifying():
    first = bind_avatar_fleet_media(
        runtime=runtime(),
        identity=identity(),
        voice_registration=voice_registration(),
        visual_registration=visual_registration(),
    )
    second = bind_avatar_fleet_media(
        runtime=runtime(),
        identity=identity(),
        voice_registration=voice_registration(),
        visual_registration=visual_registration(),
    )
    assert first.binding_key == second.binding_key
    assert first.voice_ready is True
    assert first.visual_ready is True
    assert first.multimodal_ready is True
    with pytest.raises(ValueError, match="binding key mismatch"):
        replace(first, binding_key="avatar-media:forged").validate()


def test_binding_never_grants_render_or_business_authority():
    value = bind_avatar_fleet_media(
        runtime=runtime(),
        identity=identity(visual=False),
        voice_registration=voice_registration(),
    )
    assert value.media_binding_only is True
    assert value.render_execution is False
    assert value.meeting_transmission_authority is False
    assert value.speech_execution_allowed is False
    assert value.visual_execution_allowed is False
    assert value.commercial_execution_allowed is False
    assert value.payment_execution_allowed is False
    assert value.revenue_recognition_allowed is False
    assert value.execution_authority == "none"
