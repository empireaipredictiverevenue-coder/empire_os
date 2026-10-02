from empire_os.digital_avatar import AvatarMeetingMode, AvatarMeetingSession
from empire_os.digital_avatar_authority import AvatarCommercialAuthorityDecision
from empire_os.digital_avatar_turn import (
    AvatarClaimTruth,
    AvatarTurnClaim,
    AvatarTurnDraft,
    AvatarTurnPurpose,
    assess_avatar_turn_for_approval,
)


def session():
    return AvatarMeetingSession(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        provider="meeting-gateway",
        mode=AvatarMeetingMode.COPILOT,
    )


def draft(purpose=AvatarTurnPurpose.ANSWER, claims=None):
    return AvatarTurnDraft(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        purpose=purpose,
        text="Based on the verified evidence, the pilot is the bounded next step.",
        claims=tuple(claims or ()),
        strategy_evidence_refs=("strategy:meeting-001:v1",),
    )


def test_grounded_turn_is_ready_for_human_approval_but_cannot_speak():
    decision = assess_avatar_turn_for_approval(
        session=session(),
        draft=draft(claims=[
            AvatarTurnClaim(
                text="The approved pilot is available.",
                truth_class=AvatarClaimTruth.VERIFIED,
                evidence_refs=("catalog:pilot:v1",),
            )
        ]),
    )
    assert decision.ready_for_human_approval is True
    assert decision.requires_explicit_human_approval is True
    assert decision.speech_execution_allowed is False
    assert decision.chat_execution_allowed is False
    assert decision.execution_authority == "none"


def test_unsupported_material_claim_blocks_approval():
    decision = assess_avatar_turn_for_approval(
        session=session(),
        draft=draft(claims=[
            AvatarTurnClaim(
                text="This will increase revenue by 40 percent.",
                truth_class=AvatarClaimTruth.FORECAST,
                evidence_refs=(),
            )
        ]),
    )
    assert decision.ready_for_human_approval is False
    assert decision.unsupported_claim_count == 1
    assert "material_claim_evidence_missing" in decision.blockers


def test_commercial_close_requires_authority_decision():
    decision = assess_avatar_turn_for_approval(
        session=session(),
        draft=draft(
            purpose=AvatarTurnPurpose.COMMERCIAL_CLOSE,
            claims=[
                AvatarTurnClaim(
                    text="The approved price is available.",
                    truth_class=AvatarClaimTruth.VERIFIED,
                    evidence_refs=("pricing:pilot:v1",),
                )
            ],
        ),
    )
    assert decision.ready_for_human_approval is False
    assert decision.human_takeover_required is True
    assert "commercial_authority_decision_missing" in decision.blockers


def test_in_policy_close_can_reach_human_approval_gate_only():
    commercial = AvatarCommercialAuthorityDecision(
        policy_eligible=True,
        execution_allowed=False,
        human_takeover_required=False,
        discount_bps=0,
        blockers=("runtime_observe_only",),
    )
    decision = assess_avatar_turn_for_approval(
        session=session(),
        draft=draft(
            purpose=AvatarTurnPurpose.COMMERCIAL_CLOSE,
            claims=[
                AvatarTurnClaim(
                    text="The approved pilot is $5,000.",
                    truth_class=AvatarClaimTruth.VERIFIED,
                    evidence_refs=("pricing:pilot:v1",),
                )
            ],
        ),
        commercial_authority=commercial,
    )
    assert decision.ready_for_human_approval is True
    assert decision.speech_execution_allowed is False
    assert decision.human_takeover_required is False


def test_out_of_policy_close_forces_takeover():
    commercial = AvatarCommercialAuthorityDecision(
        policy_eligible=False,
        execution_allowed=False,
        human_takeover_required=True,
        discount_bps=2000,
        blockers=("discount_exceeds_delegated_limit", "runtime_observe_only"),
    )
    decision = assess_avatar_turn_for_approval(
        session=session(),
        draft=draft(
            purpose=AvatarTurnPurpose.COMMERCIAL_CLOSE,
            claims=[
                AvatarTurnClaim(
                    text="The buyer requested a custom discount.",
                    truth_class=AvatarClaimTruth.OBSERVED,
                    evidence_refs=("meeting:event:discount-request",),
                )
            ],
        ),
        commercial_authority=commercial,
    )
    assert decision.ready_for_human_approval is False
    assert decision.human_takeover_required is True
    assert "commercial_close_outside_delegated_policy" in decision.blockers
