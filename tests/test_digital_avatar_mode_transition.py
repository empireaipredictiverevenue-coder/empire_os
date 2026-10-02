from empire_os.digital_avatar import AvatarMeetingMode, AvatarMeetingSession
from empire_os.digital_avatar_mode_transition import (
    AvatarModeTransitionEvidence,
    assess_avatar_mode_transition,
)


def session(mode, disclosed=True):
    return AvatarMeetingSession(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        provider="recall",
        mode=mode,
        disclosure_announced=disclosed,
    )


def test_shadow_to_copilot_requires_owner_approval_and_stays_non_executing():
    decision = assess_avatar_mode_transition(
        session=session(AvatarMeetingMode.SHADOW),
        target_mode=AvatarMeetingMode.COPILOT,
        evidence=AvatarModeTransitionEvidence(
            owner_approval_evidence_ref="approval:owner:1",
        ),
    )
    assert decision.policy_eligible is True
    assert decision.execution_allowed is False
    assert decision.blockers == ("runtime_observe_only",)


def test_skip_level_transition_is_blocked():
    decision = assess_avatar_mode_transition(
        session=session(AvatarMeetingMode.SHADOW),
        target_mode=AvatarMeetingMode.REPRESENT,
        evidence=AvatarModeTransitionEvidence(
            owner_approval_evidence_ref="approval:owner:1",
        ),
    )
    assert decision.policy_eligible is False
    assert "mode_transition_must_be_single_step" in decision.blockers


def test_represent_to_negotiate_requires_delegated_authority():
    decision = assess_avatar_mode_transition(
        session=session(AvatarMeetingMode.REPRESENT),
        target_mode=AvatarMeetingMode.NEGOTIATE,
        evidence=AvatarModeTransitionEvidence(
            owner_approval_evidence_ref="approval:owner:2",
        ),
    )
    assert decision.policy_eligible is False
    assert "delegated_authority_evidence_missing" in decision.blockers


def test_negotiate_to_close_requires_terms_and_authority():
    decision = assess_avatar_mode_transition(
        session=session(AvatarMeetingMode.NEGOTIATE),
        target_mode=AvatarMeetingMode.CLOSE,
        evidence=AvatarModeTransitionEvidence(
            owner_approval_evidence_ref="approval:owner:3",
            delegated_authority_evidence_ref="authority:close:v1",
            commercial_terms_evidence_ref="terms:pilot:v1",
        ),
    )
    assert decision.policy_eligible is True
    assert decision.execution_allowed is False
    assert decision.blockers == ("runtime_observe_only",)


def test_any_mode_can_fail_safe_to_shadow():
    decision = assess_avatar_mode_transition(
        session=session(AvatarMeetingMode.CLOSE),
        target_mode=AvatarMeetingMode.SHADOW,
    )
    assert decision.policy_eligible is True
    assert decision.emergency_shadow_available is True
    assert decision.execution_allowed is False
