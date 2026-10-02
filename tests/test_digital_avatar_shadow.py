from empire_os.digital_avatar import (
    AvatarMeetingMode,
    AvatarMeetingSession,
    DigitalAvatarIdentity,
)
from empire_os.digital_avatar_authority import (
    AvatarCloseProposal,
    AvatarCommercialAuthorityPolicy,
)
from empire_os.digital_avatar_shadow import build_shadow_guidance
from empire_os.meeting_gateway import (
    MeetingObservation,
    MeetingObservationKind,
    MeetingPlatform,
    MeetingSpeakerRole,
    build_shadow_meeting_state,
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


def session():
    return AvatarMeetingSession(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        provider="meeting-gateway",
        mode=AvatarMeetingMode.SHADOW,
    )


def state_with_buyer_turn():
    observation = MeetingObservation(
        meeting_id="meeting-001",
        external_meeting_id="teams-abc",
        platform=MeetingPlatform.MICROSOFT_TEAMS,
        provider_event_id="evt-1",
        kind=MeetingObservationKind.TRANSCRIPT_TURN,
        occurred_at="2026-10-02T16:00:00+00:00",
        evidence_ref="provider:teams:evt-1",
        speaker_ref="buyer-1",
        speaker_role=MeetingSpeakerRole.BUYER,
        text="Implementation timing is our biggest concern.",
    )
    return build_shadow_meeting_state(
        session=session(),
        observations=[observation],
    )


def predictive_inputs():
    return {
        "demand": 0.8,
        "quality": 0.9,
        "enrichment": 0.9,
        "omega_qualification": 0.8,
        "buyer_match": 0.75,
        "outreach": 0.7,
        "conversion": 0.6,
        "terms": 0.8,
        "payment": 0.9,
        "fulfilment": 0.95,
        "ltv_cents": 500000,
    }


def test_shadow_guidance_uses_observed_buyer_turn_privately():
    guidance = build_shadow_guidance(
        identity=identity(),
        session=session(),
        state=state_with_buyer_turn(),
        account_name="Example Buyer",
        objective="qualify fit and agree next step",
        proof_refs=("evidence:case:7",),
        commercial_terms_ref="terms:approved:v1",
        predictive_inputs=predictive_inputs(),
        action_candidates=[{
            "action_key": "ask_implementation_deadline",
            "probability_action_changes_outcome": 0.7,
            "incremental_revenue_if_changed_cents": 100000,
            "action_cost_cents": 0,
            "confidence": 0.9,
        }],
    )
    assert guidance.latest_buyer_utterance["text"] == (
        "Implementation timing is our biggest concern."
    )
    assert guidance.recommended_action["action_key"] == (
        "ask_implementation_deadline"
    )
    assert guidance.private_to_owner is True
    assert guidance.speech_execution is False
    assert guidance.meeting_action_execution is False
    assert guidance.execution_authority == "none"


def test_shadow_guidance_preserves_missing_live_buyer_signal():
    empty = build_shadow_meeting_state(
        session=session(),
        observations=[],
    )
    guidance = build_shadow_guidance(
        identity=identity(),
        session=session(),
        state=empty,
        account_name="Example Buyer",
        objective="prepare discovery",
        proof_refs=("evidence:public:1",),
        commercial_terms_ref="terms:approved:v1",
    )
    assert "buyer_utterance_not_observed" in guidance.blockers
    assert guidance.private_to_owner is True
    assert guidance.speech_execution is False


def test_shadow_guidance_marks_commercial_proposal_within_policy():
    guidance = build_shadow_guidance(
        identity=identity(),
        session=session(),
        state=state_with_buyer_turn(),
        account_name="Example Buyer",
        objective="qualify fit and agree next step",
        proof_refs=("evidence:case:7",),
        commercial_terms_ref="terms:pilot:v1",
        commercial_policy=AvatarCommercialAuthorityPolicy(
            allowed_product_codes=("predictive-revenue-pilot",),
            approved_terms_refs=("terms:pilot:v1",),
            max_discount_bps=1000,
            max_contract_months=3,
        ),
        close_proposal=AvatarCloseProposal(
            product_code="predictive-revenue-pilot",
            list_price_cents=500000,
            proposed_price_cents=475000,
            currency="USD",
            contract_months=1,
            terms_ref="terms:pilot:v1",
            evidence_refs=("pricing:pilot:v1",),
        ),
    )
    assert guidance.commercial_authority["policy_eligible"] is True
    assert guidance.commercial_authority["execution_allowed"] is False
    assert guidance.human_takeover_required is False


def test_shadow_guidance_requires_takeover_for_excess_discount():
    guidance = build_shadow_guidance(
        identity=identity(),
        session=session(),
        state=state_with_buyer_turn(),
        account_name="Example Buyer",
        objective="qualify fit and agree next step",
        proof_refs=("evidence:case:7",),
        commercial_terms_ref="terms:pilot:v1",
        commercial_policy=AvatarCommercialAuthorityPolicy(
            allowed_product_codes=("predictive-revenue-pilot",),
            approved_terms_refs=("terms:pilot:v1",),
            max_discount_bps=500,
            max_contract_months=3,
        ),
        close_proposal=AvatarCloseProposal(
            product_code="predictive-revenue-pilot",
            list_price_cents=500000,
            proposed_price_cents=450000,
            currency="USD",
            contract_months=1,
            terms_ref="terms:pilot:v1",
            evidence_refs=("pricing:pilot:v1",),
        ),
    )
    assert guidance.human_takeover_required is True
    assert "commercial_human_takeover_required" in guidance.blockers
    assert "discount_exceeds_delegated_limit" in (
        guidance.commercial_authority["blockers"]
    )
