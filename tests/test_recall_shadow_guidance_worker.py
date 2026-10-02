from empire_os.digital_avatar import (
    AvatarMeetingMode,
    AvatarMeetingSession,
    DigitalAvatarIdentity,
)
from empire_os.meeting_gateway import (
    MeetingObservation,
    MeetingObservationKind,
    MeetingPlatform,
    MeetingSpeakerRole,
)
from empire_os.recall_shadow_guidance_worker import (
    build_recall_shadow_guidance_snapshot,
)
from empire_os.recall_shadow_session import RecallShadowSessionManifest


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


def manifest():
    return RecallShadowSessionManifest(
        identity=DigitalAvatarIdentity(
            avatar_id="avatar-phil-v1",
            owner_name="Phil Livesley",
            display_name="Phil — Empire AI Digital Avatar",
            organisation_name="Empire AI",
            disclosure_text="I am Phil's authorised Empire AI Digital Avatar.",
            owner_consent_evidence_ref="consent:phil:avatar:v1",
        ),
        session=AvatarMeetingSession(
            meeting_id="meeting-001",
            avatar_id="avatar-phil-v1",
            provider="recall",
            mode=AvatarMeetingMode.SHADOW,
        ),
        account_name="Example Buyer",
        objective="qualify fit and agree next step",
        recording_consent_evidence_ref="consent:meeting:001",
        proof_refs=("evidence:case:7",),
        commercial_terms_ref="terms:pilot:v1",
        predictive_inputs=predictive_inputs(),
        action_candidates=({
            "action_key": "ask_implementation_deadline",
            "probability_action_changes_outcome": 0.6,
            "incremental_revenue_if_changed_cents": 100000,
            "action_cost_cents": 0,
            "confidence": 0.9,
        },),
        participant_roles={
            "recall-participant:7": MeetingSpeakerRole.BUYER,
        },
    )


def buyer_observation():
    return MeetingObservation(
        meeting_id="meeting-001",
        external_meeting_id="bot-123",
        platform=MeetingPlatform.ZOOM,
        provider_event_id="evt-1",
        kind=MeetingObservationKind.TRANSCRIPT_TURN,
        occurred_at="2026-10-02T18:00:00+00:00",
        evidence_ref="recall:bot-123:transcript-456:abc",
        speaker_ref="recall-participant:7",
        speaker_name="Buyer",
        speaker_role=MeetingSpeakerRole.UNKNOWN,
        text="We need this live before November.",
        is_final=True,
    )


def test_manifest_role_binding_unlocks_private_buyer_guidance():
    snapshot = build_recall_shadow_guidance_snapshot(
        manifest=manifest(),
        observations=[buyer_observation()],
    )
    latest = snapshot.guidance.latest_buyer_utterance
    assert latest["speaker_role"] == "buyer"
    assert latest["text"] == "We need this live before November."
    assert snapshot.guidance.recommended_action["action_key"] == (
        "ask_implementation_deadline"
    )
    assert snapshot.response_task is not None
    assert snapshot.response_task.requires_human_approval is True
    assert snapshot.response_task.speech_execution_allowed is False
    assert snapshot.private_to_owner is True
    assert snapshot.execution_authority == "none"


def test_unknown_speaker_without_binding_does_not_become_buyer():
    item = manifest()
    object.__setattr__(item, "participant_roles", {})
    snapshot = build_recall_shadow_guidance_snapshot(
        manifest=item,
        observations=[buyer_observation()],
    )
    assert snapshot.guidance.latest_buyer_utterance is None
    assert snapshot.response_task is None
    assert "buyer_utterance_not_observed" in snapshot.guidance.blockers
