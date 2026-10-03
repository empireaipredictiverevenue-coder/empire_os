from pathlib import Path

import pytest

from empire_os.digital_avatar import (
    AvatarMeetingMode,
    AvatarMeetingSession,
    DigitalAvatarIdentity,
)
from empire_os.digital_avatar_fast_preview import (
    build_fast_preview_response_task,
    materialize_fast_private_preview,
    verify_fast_preview_against_signed_observation,
)
from empire_os.digital_avatar_presence_transcript import (
    PresenceTranscriptObservation,
)
from empire_os.meeting_gateway import (
    MeetingObservation,
    MeetingObservationKind,
    MeetingPlatform,
    MeetingSpeakerRole,
)
from empire_os.recall_shadow_session import RecallShadowSessionManifest


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
        predictive_inputs={
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
        },
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


def observation(**overrides):
    values = {
        "observation_id": "presence-transcript:abc123",
        "meeting_id": "meeting-001",
        "avatar_id": "avatar-phil-v1",
        "bot_id": "bot-123",
        "participant_ref": "recall-participant:7",
        "participant_name": "Buyer",
        "text": "Can you deploy this quickly?",
        "received_at": "2026-10-02T20:00:00+00:00",
        "is_final": True,
    }
    values.update(overrides)
    return PresenceTranscriptObservation(**values)


class Resolver:
    def __init__(self, missing=()):
        self.missing = set(missing)

    def resolve(self, evidence_ref):
        if evidence_ref in self.missing:
            return None
        data = {
            "evidence:case:7": {
                "content": "Verified deployment case evidence is available.",
                "truth_class": "VERIFIED",
                "source_kind": "commercial_evidence",
                "provenance": "empire:evidence-registry",
            },
            "terms:pilot:v1": {
                "content": "Pilot commercial terms are verified and bound.",
                "truth_class": "VERIFIED",
                "source_kind": "commercial_terms",
                "provenance": "empire:terms-registry",
            },
        }
        item = data.get(evidence_ref)
        if item is None:
            return None
        return {
            "evidence_ref": evidence_ref,
            "verified": True,
            **item,
        }


class Provider:
    provider_key = "test-grounded-provider"

    def __init__(self):
        self.calls = []

    def generate_grounded(self, task, evidence_pack):
        self.calls.append((task, evidence_pack))
        return {
            "text": (
                "Yes. I can show you the verified deployment evidence, "
                "then we can pin down your implementation deadline."
            ),
            "claims": [{
                "text": "Verified deployment case evidence is available.",
                "truth_class": "VERIFIED",
                "evidence_refs": ["evidence:case:7"],
            }],
        }


def test_fast_preview_uses_buyer_text_as_context_not_approved_evidence():
    obs = observation()
    task = build_fast_preview_response_task(
        manifest=manifest(),
        observation=obs,
    )
    assert task.latest_buyer_utterance == "Can you deploy this quickly?"
    assert obs.observation_id not in task.approved_evidence_refs
    assert task.approved_evidence_refs == (
        "evidence:case:7",
        "terms:pilot:v1",
    )
    assert "pending signed Recall verification" in task.constraints[0]
    assert task.mode == "COPILOT_FAST_PREVIEW"
    assert task.output_channel == "private_fast_preview"
    assert task.requires_human_approval is True
    assert task.speech_execution_allowed is False
    assert task.execution_authority == "none"


def test_fast_preview_can_draft_early_from_verified_empire_evidence(tmp_path):
    provider = Provider()
    packet = materialize_fast_private_preview(
        manifest=manifest(),
        observation=observation(),
        evidence_resolver=Resolver(),
        provider=provider,
        output_root=tmp_path / "fast",
    )
    assert packet.status == "preview_ready_pending_verification"
    assert packet.pending_signed_verification is True
    assert packet.private_to_owner is True
    assert packet.human_approval_required is True
    assert packet.speech_ready is False
    assert packet.transmission_performed is False
    assert packet.execution_authority == "none"
    assert packet.draft is not None
    assert packet.draft.ready_for_human_review is True
    assert len(provider.calls) == 1

    latest = tmp_path / "fast" / "meeting-001" / "latest.json"
    assert latest.is_file()
    assert oct(latest.stat().st_mode & 0o777) == "0o600"


def test_fast_preview_blocks_when_verified_business_evidence_missing(tmp_path):
    provider = Provider()
    packet = materialize_fast_private_preview(
        manifest=manifest(),
        observation=observation(),
        evidence_resolver=Resolver(missing={"terms:pilot:v1"}),
        provider=provider,
        output_root=tmp_path / "fast",
    )
    assert packet.status == "blocked_evidence"
    assert packet.unresolved_refs == ("terms:pilot:v1",)
    assert packet.draft is None
    assert packet.speech_ready is False
    assert provider.calls == []


def test_fast_preview_identity_mismatch_fails_closed():
    with pytest.raises(ValueError, match="meeting/session mismatch"):
        build_fast_preview_response_task(
            manifest=manifest(),
            observation=observation(meeting_id="meeting-other"),
        )


def signed_observation(**overrides):
    values = {
        "meeting_id": "meeting-001",
        "external_meeting_id": "bot-123",
        "platform": MeetingPlatform.ZOOM,
        "provider_event_id": "recall:verified-event-1",
        "kind": MeetingObservationKind.TRANSCRIPT_TURN,
        "occurred_at": "2026-10-02T20:00:01+00:00",
        "evidence_ref": "recall:bot-123:transcript-1:abcdef123456",
        "speaker_ref": "recall-participant:7",
        "speaker_name": "Buyer",
        "speaker_role": MeetingSpeakerRole.BUYER,
        "text": "Can you deploy this quickly?",
        "is_final": True,
    }
    values.update(overrides)
    return MeetingObservation(**values)


def ready_preview(tmp_path):
    return materialize_fast_private_preview(
        manifest=manifest(),
        observation=observation(),
        evidence_resolver=Resolver(),
        provider=Provider(),
        output_root=tmp_path / "fast",
    )


def test_signed_webhook_upgrades_fast_preview_to_speech_approval_eligibility(tmp_path):
    preview = ready_preview(tmp_path)
    verified = verify_fast_preview_against_signed_observation(
        preview=preview,
        verified_observation=signed_observation(),
    )
    assert verified.signed_verification_matched is True
    assert verified.verified_evidence_ref.startswith("recall:")
    assert verified.eligible_for_human_review is True
    assert verified.eligible_for_speech_approval is True
    assert verified.speech_execution_allowed is False
    assert verified.transmission_performed is False
    assert verified.execution_authority == "none"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"text": "Different buyer text"}, "text mismatch"),
        ({"external_meeting_id": "bot-other"}, "bot mismatch"),
        ({"speaker_ref": "recall-participant:9"}, "participant mismatch"),
        ({"is_final": False}, "final transcript"),
    ],
)
def test_signed_upgrade_fails_closed_on_mismatch(tmp_path, kwargs, message):
    with pytest.raises(ValueError, match=message):
        verify_fast_preview_against_signed_observation(
            preview=ready_preview(tmp_path),
            verified_observation=signed_observation(**kwargs),
        )


def test_signed_match_does_not_make_blocked_preview_speech_eligible(tmp_path):
    preview = materialize_fast_private_preview(
        manifest=manifest(),
        observation=observation(),
        evidence_resolver=Resolver(missing={"terms:pilot:v1"}),
        provider=Provider(),
        output_root=tmp_path / "fast",
    )
    verified = verify_fast_preview_against_signed_observation(
        preview=preview,
        verified_observation=signed_observation(),
    )
    assert verified.signed_verification_matched is True
    assert verified.eligible_for_human_review is False
    assert verified.eligible_for_speech_approval is False
    assert verified.speech_execution_allowed is False
