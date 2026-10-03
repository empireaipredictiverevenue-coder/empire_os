import pytest

from empire_os.digital_avatar import DigitalAvatarIdentity
from empire_os.digital_avatar_authority import (
    AvatarCloseProposal,
    AvatarCommercialAuthorityPolicy,
)
from empire_os.recall_shadow_activation import prepare_recall_shadow_activation
from empire_os.recall_shadow_join import RecallShadowJoinApproval


def identity():
    return DigitalAvatarIdentity(
        avatar_id="avatar-phil-v1",
        owner_name="Phil Livesley",
        display_name="Phil — Empire AI Digital Avatar",
        organisation_name="Empire AI",
        disclosure_text="I am Phil's authorised Empire AI Digital Avatar.",
        owner_consent_evidence_ref="consent:phil:avatar:v1",
    )


def approval():
    return RecallShadowJoinApproval(
        meeting_id="meeting-001",
        approved_by="Phil Livesley",
        approval_evidence_ref="approval:recall-shadow:meeting-001:v1",
        approved_at="2026-10-02T18:00:00+00:00",
        expires_at="2026-10-02T20:00:00+00:00",
    )


def prepare(**overrides):
    values = {
        "identity": identity(),
        "meeting_id": "meeting-001",
        "platform": "zoom",
        "meeting_url": "https://zoom.us/j/123456789",
        "bot_name": "Phil — Empire AI Digital Avatar",
        "public_realtime_url": (
            "https://empire-ai.co.uk/v1/providers/recall/realtime"
        ),
        "account_name": "Example Buyer",
        "objective": "qualify fit and agree next step",
        "owner_join_approval": approval(),
        "region": "eu-central-1",
        "now": "2026-10-02T18:30:00+00:00",
        "recording_consent_evidence_ref": "consent:meeting:001",
        "webhook_verification_evidence_ref": "config:recall-signing:v1",
    }
    values.update(overrides)
    return prepare_recall_shadow_activation(**values)


def test_activation_packet_keeps_all_execution_except_join_off():
    packet = prepare()
    assert packet.live_join_prepared is True
    assert packet.live_join_performed is False
    assert packet.speech_execution is False
    assert packet.chat_send_execution is False
    assert packet.commercial_execution is False
    assert packet.execution_authority == "shadow_join_only"
    assert packet.manifest.session.meeting_id == "meeting-001"
    assert packet.bot_plan.request_body["metadata"]["empire_meeting_id"] == (
        "meeting-001"
    )
    assert packet.join_request.meeting_id == "meeting-001"


def test_activation_rejects_approval_for_other_meeting():
    wrong = approval()
    object.__setattr__(wrong, "meeting_id", "meeting-999")
    with pytest.raises(ValueError, match="meeting mismatch"):
        prepare(owner_join_approval=wrong)


def test_activation_rejects_missing_consent():
    with pytest.raises(ValueError, match="recording consent evidence"):
        prepare(recording_consent_evidence_ref="")


def test_participant_roles_are_explicit_not_inferred():
    packet = prepare(
        participant_roles={
            "recall-participant:7": "buyer",
            "recall-participant:9": "avatar_owner",
        }
    )
    roles = packet.manifest.participant_roles
    assert roles["recall-participant:7"].value == "buyer"
    assert roles["recall-participant:9"].value == "avatar_owner"


def test_activation_binds_delegated_close_envelope_without_execution():
    terms_ref = "commercial_terms_review:22222222-2222-4222-8222-222222222222"
    policy = AvatarCommercialAuthorityPolicy(
        allowed_product_codes=("PREDICTIVE-REVENUE-PILOT",),
        approved_terms_refs=(terms_ref,),
        allowed_currencies=("USD",),
        max_discount_bps=1000,
        max_contract_months=3,
    )
    proposal = AvatarCloseProposal(
        product_code="PREDICTIVE-REVENUE-PILOT",
        list_price_cents=500000,
        proposed_price_cents=475000,
        currency="USD",
        contract_months=1,
        terms_ref=terms_ref,
        evidence_refs=(
            "commercial_product_code:PREDICTIVE-REVENUE-PILOT",
            "commercial_evidence:11111111-1111-4111-8111-111111111111",
        ),
    )
    packet = prepare(
        commercial_terms_ref=terms_ref,
        commercial_policy=policy,
        close_proposal=proposal,
    )
    assert packet.manifest.commercial_policy == policy
    assert packet.manifest.close_proposal == proposal
    assert packet.live_join_performed is False
    assert packet.speech_execution is False
    assert packet.commercial_execution is False
    assert packet.execution_authority == "shadow_join_only"
