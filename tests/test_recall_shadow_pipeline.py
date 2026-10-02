import pytest

from empire_os.digital_avatar import (
    AvatarMeetingMode,
    AvatarMeetingSession,
    DigitalAvatarIdentity,
)
from empire_os.meeting_gateway import MeetingPlatform
from empire_os.recall_shadow_pipeline import (
    RecallVerifiedEvent,
    build_recall_shadow_pipeline_preview,
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
        provider="recall",
        mode=AvatarMeetingMode.SHADOW,
    )


def transcript_event(text_words, *, event="transcript.data"):
    return {
        "event": event,
        "data": {
            "bot": {"id": "bot-123"},
            "transcript": {"id": "transcript-456"},
            "data": {
                "participant": {"id": 7, "name": "Buyer"},
                "words": [{"text": word} for word in text_words],
            },
        },
    }


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


def actions():
    return [{
        "action_key": "ask_implementation_deadline",
        "probability_action_changes_outcome": 0.6,
        "incremental_revenue_if_changed_cents": 100000,
        "action_cost_cents": 0,
        "confidence": 0.9,
    }]


def test_verified_event_flows_to_private_shadow_guidance():
    preview = build_recall_shadow_pipeline_preview(
        identity=identity(),
        session=session(),
        platform=MeetingPlatform.ZOOM,
        events=[RecallVerifiedEvent(
            payload=transcript_event(["We", "need", "this", "soon"]),
            received_at="2026-10-02T18:00:00+00:00",
            verified=True,
        )],
        participant_roles={"7": "buyer"},
        account_name="Example Buyer",
        objective="qualify fit and agree next step",
        proof_refs=("evidence:case:7",),
        commercial_terms_ref="terms:pilot:v1",
        predictive_inputs=predictive_inputs(),
        action_candidates=actions(),
    )
    assert preview.event_count == 1
    assert preview.verified_event_count == 1
    assert preview.meeting_state.latest_buyer_utterance["text"] == "We need this soon"
    assert preview.meeting_memory.truth_class == "OBSERVED"
    assert preview.meeting_memory.summary_generated is False
    assert preview.meeting_memory.inference_performed is False
    assert preview.meeting_memory.buyer_turns[0]["text"] == "We need this soon"
    assert preview.guidance.recommended_action["action_key"] == "ask_implementation_deadline"
    assert preview.guidance.private_to_owner is True
    assert preview.response_task.recommended_action_key == "ask_implementation_deadline"
    assert preview.response_task.requires_human_approval is True
    assert preview.response_task.speech_execution_allowed is False
    assert preview.speech_execution is False
    assert preview.execution_authority == "none"


def test_pipeline_rejects_any_unverified_event():
    with pytest.raises(ValueError, match="unverified Recall event rejected"):
        build_recall_shadow_pipeline_preview(
            identity=identity(),
            session=session(),
            platform=MeetingPlatform.ZOOM,
            events=[RecallVerifiedEvent(
                payload=transcript_event(["Hello"]),
                received_at="2026-10-02T18:00:00+00:00",
                verified=False,
            )],
            account_name="Example Buyer",
            objective="discovery",
        )


def test_pipeline_requires_events():
    with pytest.raises(ValueError, match="at least one verified Recall event required"):
        build_recall_shadow_pipeline_preview(
            identity=identity(),
            session=session(),
            platform=MeetingPlatform.ZOOM,
            events=[],
            account_name="Example Buyer",
            objective="discovery",
        )
