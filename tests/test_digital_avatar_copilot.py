import pytest

from empire_os.digital_avatar import (
    AvatarMeetingMode,
    AvatarMeetingSession,
    DigitalAvatarIdentity,
)
from empire_os.digital_avatar_copilot import build_avatar_copilot_handoff
from empire_os.digital_avatar_turn import (
    AvatarClaimTruth,
    AvatarTurnClaim,
    AvatarTurnDraft,
    AvatarTurnPurpose,
)


def identity():
    return DigitalAvatarIdentity(
        avatar_id="avatar-phil-v1",
        owner_name="Phil Livesley",
        display_name="Phil — Empire AI Digital Avatar",
        organisation_name="Empire AI",
        disclosure_text="I am Phil's authorised Empire AI Digital Avatar.",
        owner_consent_evidence_ref="consent:phil:avatar:v1",
    )


def copilot_session():
    return AvatarMeetingSession(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        provider="recall",
        mode=AvatarMeetingMode.COPILOT,
        disclosure_announced=True,
    )


def grounded_draft():
    return AvatarTurnDraft(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        purpose=AvatarTurnPurpose.ANSWER,
        text="The approved pilot is available at the verified price.",
        claims=(
            AvatarTurnClaim(
                text="The approved pilot is available.",
                truth_class=AvatarClaimTruth.VERIFIED,
                evidence_refs=("catalog:pilot:v1",),
            ),
        ),
        strategy_evidence_refs=("strategy:meeting-001:v1",),
    )


def test_grounded_copilot_handoff_is_ready_but_never_transmits():
    handoff = build_avatar_copilot_handoff(
        identity=identity(),
        session=copilot_session(),
        draft=grounded_draft(),
    )
    assert handoff.ready_for_human_approval is True
    assert handoff.human_approval_required is True
    assert handoff.human_approval_recorded is False
    assert handoff.transmission_performed is False
    assert handoff.speech_execution_allowed is False
    assert handoff.chat_execution_allowed is False
    assert handoff.execution_authority == "none"


def test_unsupported_claim_blocks_handoff_readiness():
    draft = AvatarTurnDraft(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        purpose=AvatarTurnPurpose.ANSWER,
        text="We can guarantee that outcome.",
        claims=(
            AvatarTurnClaim(
                text="We can guarantee that outcome.",
                truth_class=AvatarClaimTruth.FORECAST,
                evidence_refs=(),
            ),
        ),
        strategy_evidence_refs=("strategy:meeting-001:v1",),
    )
    handoff = build_avatar_copilot_handoff(
        identity=identity(),
        session=copilot_session(),
        draft=draft,
    )
    assert handoff.ready_for_human_approval is False
    assert "material_claim_evidence_missing" in handoff.decision.blockers


def test_shadow_mode_cannot_create_copilot_handoff():
    shadow = AvatarMeetingSession(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        provider="recall",
        mode=AvatarMeetingMode.SHADOW,
    )
    with pytest.raises(ValueError, match="requires COPILOT mode"):
        build_avatar_copilot_handoff(
            identity=identity(),
            session=shadow,
            draft=grounded_draft(),
        )
