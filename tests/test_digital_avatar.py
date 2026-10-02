import pytest

from empire_os.digital_avatar import (
    AvatarAction,
    AvatarAuthorityEnvelope,
    AvatarCommercialContext,
    AvatarMeetingMode,
    AvatarMeetingSession,
    DigitalAvatarIdentity,
    evaluate_avatar_action,
)


def identity() -> DigitalAvatarIdentity:
    return DigitalAvatarIdentity(
        avatar_id="avatar-phil-v1",
        owner_name="Phil Livesley",
        display_name="Phil — Empire AI Digital Avatar",
        organisation_name="Empire AI",
        disclosure_text="I am Phil's authorised Empire AI Digital Avatar.",
        owner_consent_evidence_ref="consent:phil:avatar:v1",
    )


def session(mode: AvatarMeetingMode, *, disclosed: bool = True) -> AvatarMeetingSession:
    return AvatarMeetingSession(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        provider="provider-test",
        mode=mode,
        disclosure_announced=disclosed,
    )


def full_authority() -> AvatarAuthorityEnvelope:
    return AvatarAuthorityEnvelope(
        can_answer_business_questions=True,
        can_quote_verified_price=True,
        can_negotiate=True,
        can_close_within_terms=True,
        can_prepare_follow_up=True,
        max_discount_bps=1000,
    )


def test_identity_requires_explicit_ai_disclosure():
    item = DigitalAvatarIdentity(
        avatar_id="avatar-1",
        owner_name="Owner",
        display_name="Owner representative",
        organisation_name="Business",
        disclosure_text="I represent the owner.",
        owner_consent_evidence_ref="consent:1",
    )
    with pytest.raises(ValueError, match="explicitly identify AI"):
        item.validate()


def test_prepare_response_is_internal_and_allowed_in_observe():
    decision = evaluate_avatar_action(
        identity=identity(),
        authority=AvatarAuthorityEnvelope(),
        session=session(AvatarMeetingMode.SHADOW, disclosed=False),
        action=AvatarAction.PREPARE_RESPONSE,
    )
    assert decision.allowed is True
    assert decision.execution_authority == "none"
    assert decision.side_effects is False


def test_shadow_mode_cannot_speak_and_observe_runtime_blocks_execution():
    decision = evaluate_avatar_action(
        identity=identity(),
        authority=AvatarAuthorityEnvelope(),
        session=session(AvatarMeetingMode.SHADOW),
        action=AvatarAction.SPEAK,
    )
    assert decision.allowed is False
    assert "shadow_mode_cannot_speak" in decision.blockers
    assert "runtime_observe_only" in decision.blockers


def test_close_mode_still_cannot_execute_in_v1():
    decision = evaluate_avatar_action(
        identity=identity(),
        authority=full_authority(),
        session=session(AvatarMeetingMode.CLOSE),
        action=AvatarAction.CLOSE,
        commercial=AvatarCommercialContext(
            opportunity_id="opp-001",
            verified_price_cents=500000,
            commercial_terms_verified=True,
            evidence_refs=("terms:opp-001:v1",),
        ),
    )
    assert decision.allowed is False
    assert decision.blockers == ("runtime_observe_only",)


def test_negotiation_rejects_discount_above_delegated_limit():
    decision = evaluate_avatar_action(
        identity=identity(),
        authority=full_authority(),
        session=session(AvatarMeetingMode.NEGOTIATE),
        action=AvatarAction.NEGOTIATE,
        commercial=AvatarCommercialContext(
            verified_price_cents=500000,
            proposed_discount_bps=1500,
            commercial_terms_verified=True,
        ),
    )
    assert decision.allowed is False
    assert "discount_exceeds_delegated_limit" in decision.blockers
    assert "runtime_observe_only" in decision.blockers


def test_external_action_requires_disclosure():
    decision = evaluate_avatar_action(
        identity=identity(),
        authority=full_authority(),
        session=session(AvatarMeetingMode.REPRESENT, disclosed=False),
        action=AvatarAction.QUOTE,
        commercial=AvatarCommercialContext(verified_price_cents=250000),
    )
    assert decision.allowed is False
    assert "ai_disclosure_not_announced" in decision.blockers


def test_v1_rejects_attempt_to_expand_runtime_authority():
    with pytest.raises(ValueError, match="OBSERVE only"):
        evaluate_avatar_action(
            identity=identity(),
            authority=full_authority(),
            session=session(AvatarMeetingMode.CLOSE),
            action=AvatarAction.CLOSE,
            commercial=AvatarCommercialContext(
                verified_price_cents=500000,
                commercial_terms_verified=True,
            ),
            runtime_authority="governed_external",
        )


def test_authority_envelope_rejects_close_without_negotiation():
    with pytest.raises(ValueError, match="close authority requires negotiation"):
        AvatarAuthorityEnvelope(
            can_quote_verified_price=True,
            can_negotiate=False,
            can_close_within_terms=True,
        ).validate()
