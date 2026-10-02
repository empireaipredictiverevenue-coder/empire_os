from empire_os.digital_avatar import (
    AvatarMeetingMode,
    AvatarMeetingSession,
    DigitalAvatarIdentity,
)
from empire_os.digital_avatar_strategy import build_avatar_meeting_strategy


def identity() -> DigitalAvatarIdentity:
    return DigitalAvatarIdentity(
        avatar_id="avatar-phil-v1",
        owner_name="Phil Livesley",
        display_name="Phil — Empire AI Digital Avatar",
        organisation_name="Empire AI",
        disclosure_text="I am Phil's authorised Empire AI Digital Avatar.",
        owner_consent_evidence_ref="consent:phil:avatar:v1",
    )


def session() -> AvatarMeetingSession:
    return AvatarMeetingSession(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        provider="provider-test",
        mode=AvatarMeetingMode.SHADOW,
        disclosure_announced=False,
    )


def predictive_inputs():
    values = {
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
    return values


def action_candidates():
    return [
        {
            "action_key": "ask_implementation_deadline",
            "probability_action_changes_outcome": 0.5,
            "incremental_revenue_if_changed_cents": 100000,
            "action_cost_cents": 0,
            "confidence": 0.9,
        },
        {
            "action_key": "present_verified_case_evidence",
            "probability_action_changes_outcome": 0.7,
            "incremental_revenue_if_changed_cents": 100000,
            "action_cost_cents": 0,
            "confidence": 0.9,
        },
    ]


def test_strategy_uses_predictive_revenue_and_next_best_action():
    packet = build_avatar_meeting_strategy(
        identity=identity(),
        session=session(),
        account_name="Example Buyer",
        objective="qualify fit and agree next step",
        buyer_signal_summary="Buyer requested implementation detail",
        buyer_signal_evidence_refs=("conversation:event:42",),
        proof_refs=("evidence:case:7",),
        commercial_terms_ref="terms:product:approved:v1",
        predictive_inputs=predictive_inputs(),
        action_candidates=action_candidates(),
    )
    assert packet.predictive_revenue["status"] == "AVAILABLE"
    assert packet.next_best_action["action_key"] == "present_verified_case_evidence"
    assert packet.blockers == ()
    assert packet.execution_authority == "none"
    assert packet.actual_revenue is False


def test_strategy_preserves_unknown_predictive_inputs():
    packet = build_avatar_meeting_strategy(
        identity=identity(),
        session=session(),
        account_name="Example Buyer",
        objective="prepare discovery",
        proof_refs=("evidence:public:1",),
        commercial_terms_ref="terms:product:approved:v1",
    )
    assert packet.predictive_revenue["status"] == "UNAVAILABLE"
    assert "predictive_revenue_inputs_incomplete" in packet.blockers
    assert "next_best_action_unavailable" in packet.blockers


def test_strategy_requires_signal_evidence_when_signal_is_claimed():
    packet = build_avatar_meeting_strategy(
        identity=identity(),
        session=session(),
        account_name="Example Buyer",
        objective="prepare discovery",
        buyer_signal_summary="Buyer appears urgent",
        proof_refs=("evidence:public:1",),
        commercial_terms_ref="terms:product:approved:v1",
    )
    assert "buyer_signal_evidence_missing" in packet.blockers


def test_strategy_blocks_commercial_readiness_without_bound_terms():
    packet = build_avatar_meeting_strategy(
        identity=identity(),
        session=session(),
        account_name="Example Buyer",
        objective="prepare commercial conversation",
        proof_refs=("evidence:public:1",),
        predictive_inputs=predictive_inputs(),
        action_candidates=action_candidates(),
    )
    assert "verified_commercial_terms_not_bound" in packet.blockers
    assert packet.side_effects == "none"
