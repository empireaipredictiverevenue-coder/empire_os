from datetime import datetime, timezone

import pytest

from empire_os.digital_avatar import (
    AvatarMeetingMode,
    AvatarMeetingSession,
    DigitalAvatarIdentity,
)
from empire_os.digital_avatar_copilot import build_avatar_copilot_handoff
from empire_os.digital_avatar_speech import (
    AvatarHumanTurnApproval,
    build_avatar_speech_render_task,
    speech_text_sha256,
)
from empire_os.digital_avatar_turn import (
    AvatarClaimTruth,
    AvatarTurnClaim,
    AvatarTurnDraft,
    AvatarTurnPurpose,
)
from empire_os.digital_avatar_voice_profile import (
    AvatarVoiceProfile,
    build_avatar_voice_render_plan,
)


NOW = datetime(2026, 10, 2, 18, 30, tzinfo=timezone.utc)


def speech_task():
    identity = DigitalAvatarIdentity(
        avatar_id="avatar-phil-v1",
        owner_name="Phil Livesley",
        display_name="Phil — Empire AI Digital Avatar",
        organisation_name="Empire AI",
        disclosure_text="I am Phil's authorised Empire AI Digital Avatar.",
        owner_consent_evidence_ref="consent:phil:avatar:v1",
        voice_profile_ref="voice:phil:v1",
    )
    session = AvatarMeetingSession(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        provider="recall",
        mode=AvatarMeetingMode.COPILOT,
        disclosure_announced=True,
    )
    draft = AvatarTurnDraft(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        purpose=AvatarTurnPurpose.ANSWER,
        text="Yes. I can show you the verified case evidence.",
        claims=(
            AvatarTurnClaim(
                text="Verified case evidence is available.",
                truth_class=AvatarClaimTruth.VERIFIED,
                evidence_refs=("evidence:case:7",),
            ),
        ),
        strategy_evidence_refs=("strategy:meeting-001:v1",),
    )
    handoff = build_avatar_copilot_handoff(
        identity=identity,
        session=session,
        draft=draft,
    )
    approval = AvatarHumanTurnApproval(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        approved_by="Phil Livesley",
        approval_evidence_ref="approval:speech:1",
        approved_at="2026-10-02T18:29:00+00:00",
        expires_at="2026-10-02T18:32:00+00:00",
        approved_text_sha256=speech_text_sha256(draft.text),
    )
    return build_avatar_speech_render_task(
        identity=identity,
        session=session,
        handoff=handoff,
        approval=approval,
        now=NOW,
    )


def clone_profile(engine="cosyvoice3"):
    return AvatarVoiceProfile(
        profile_ref="voice:phil:v1",
        owner_consent_evidence_ref="consent:phil:voice-clone:v1",
        reference_audio_ref="voice-media:phil:clean-ref:v1",
        reference_transcript_ref="voice-transcript:phil:clean-ref:v1",
        engine_voice_id="phil-v1",
        clone_required=True,
        preferred_engine=engine,
        language="en",
    )


def test_clone_profile_selects_cosyvoice3_and_stays_local():
    plan = build_avatar_voice_render_plan(
        task=speech_task(),
        profile=clone_profile(),
        available_engines={"cosyvoice3": True, "kokoro": True},
    )
    assert plan.engine == "cosyvoice3"
    assert plan.model_ref == "FunAudioLLM/Fun-CosyVoice3-0.5B-2512"
    assert plan.clone_required is True
    assert plan.streaming_required is True
    assert plan.local_audio_render_allowed is True
    assert plan.meeting_transmission_allowed is False
    assert plan.speech_execution_allowed is False
    assert plan.execution_authority == "none"


def test_clone_profile_cannot_fall_back_to_kokoro():
    with pytest.raises(ValueError, match="cannot use generic TTS"):
        build_avatar_voice_render_plan(
            task=speech_task(),
            profile=clone_profile("kokoro"),
            available_engines={"kokoro": True},
        )


def test_missing_clone_reference_media_fails_closed():
    profile = AvatarVoiceProfile(
        profile_ref="voice:phil:v1",
        owner_consent_evidence_ref="consent:phil:voice-clone:v1",
        reference_audio_ref=None,
        reference_transcript_ref=None,
        clone_required=True,
        preferred_engine="cosyvoice3",
    )
    with pytest.raises(ValueError, match="reference audio required"):
        build_avatar_voice_render_plan(
            task=speech_task(),
            profile=profile,
            available_engines={"cosyvoice3": True},
        )


def test_unavailable_clone_engine_does_not_silently_degrade():
    with pytest.raises(ValueError, match="voice engine unavailable"):
        build_avatar_voice_render_plan(
            task=speech_task(),
            profile=clone_profile(),
            available_engines={"cosyvoice3": False, "kokoro": True},
        )


def test_voice_profile_must_match_approved_speech_task():
    profile = AvatarVoiceProfile(
        profile_ref="voice:someone-else:v1",
        owner_consent_evidence_ref="consent:other:v1",
        reference_audio_ref="voice-media:other:v1",
        reference_transcript_ref="voice-transcript:other:v1",
        engine_voice_id="other-v1",
        clone_required=True,
        preferred_engine="cosyvoice3",
    )
    with pytest.raises(ValueError, match="voice profile identity mismatch"):
        build_avatar_voice_render_plan(
            task=speech_task(),
            profile=profile,
            available_engines={"cosyvoice3": True},
        )
