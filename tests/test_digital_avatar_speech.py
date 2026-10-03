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


NOW = datetime(2026, 10, 2, 18, 30, tzinfo=timezone.utc)


def identity(voice_profile_ref="voice:phil:v1"):
    return DigitalAvatarIdentity(
        avatar_id="avatar-phil-v1",
        owner_name="Phil Livesley",
        display_name="Phil — Empire AI Digital Avatar",
        organisation_name="Empire AI",
        disclosure_text="I am Phil's authorised Empire AI Digital Avatar.",
        owner_consent_evidence_ref="consent:phil:avatar:v1",
        voice_profile_ref=voice_profile_ref,
    )


def session(disclosed=True):
    return AvatarMeetingSession(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        provider="recall",
        mode=AvatarMeetingMode.COPILOT,
        disclosure_announced=disclosed,
    )


def handoff():
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
    return build_avatar_copilot_handoff(
        identity=identity(),
        session=session(),
        draft=draft,
    )


def approval(text=None, **overrides):
    text = text or handoff().draft_text
    values = {
        "meeting_id": "meeting-001",
        "avatar_id": "avatar-phil-v1",
        "approved_by": "Phil Livesley",
        "approval_evidence_ref": "approval:speech:meeting-001:turn-1",
        "approved_at": "2026-10-02T18:29:00+00:00",
        "expires_at": "2026-10-02T18:32:00+00:00",
        "approved_text_sha256": speech_text_sha256(text),
    }
    values.update(overrides)
    return AvatarHumanTurnApproval(**values)


def test_approved_copilot_turn_becomes_local_render_task_only():
    value = handoff()
    task = build_avatar_speech_render_task(
        identity=identity(),
        session=session(),
        handoff=value,
        approval=approval(value.draft_text),
        now=NOW,
    )
    assert task.voice_profile_ref == "voice:phil:v1"
    assert task.text == value.draft_text
    assert task.local_audio_render_allowed is True
    assert task.meeting_transmission_allowed is False
    assert task.speech_execution_allowed is False
    assert task.chat_execution_allowed is False
    assert task.commercial_execution_allowed is False
    assert task.execution_authority == "none"


def test_generic_fallback_voice_is_not_allowed_when_profile_missing():
    value = handoff()
    with pytest.raises(ValueError, match="bound avatar voice profile required"):
        build_avatar_speech_render_task(
            identity=identity(None),
            session=session(),
            handoff=value,
            approval=approval(value.draft_text),
            now=NOW,
        )


def test_changed_text_invalidates_human_speech_approval():
    value = handoff()
    wrong = approval("Different text")
    with pytest.raises(ValueError, match="text fingerprint mismatch"):
        build_avatar_speech_render_task(
            identity=identity(),
            session=session(),
            handoff=value,
            approval=wrong,
            now=NOW,
        )


def test_expired_speech_approval_is_blocked():
    value = handoff()
    expired = approval(
        value.draft_text,
        approved_at="2026-10-02T18:00:00+00:00",
        expires_at="2026-10-02T18:10:00+00:00",
    )
    with pytest.raises(ValueError, match="speech approval not active"):
        build_avatar_speech_render_task(
            identity=identity(),
            session=session(),
            handoff=value,
            approval=expired,
            now=NOW,
        )


def test_speech_requires_ai_disclosure():
    value = handoff()
    with pytest.raises(ValueError, match="AI disclosure must be announced"):
        build_avatar_speech_render_task(
            identity=identity(),
            session=session(disclosed=False),
            handoff=value,
            approval=approval(value.draft_text),
            now=NOW,
        )
