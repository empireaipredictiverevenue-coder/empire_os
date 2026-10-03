from dataclasses import replace

import pytest

from empire_os.digital_avatar import (
    AvatarMeetingMode,
    DigitalAvatarIdentity,
)
from empire_os.digital_avatar_fleet import AvatarFleetRuntimeBinding
from empire_os.digital_avatar_fleet_dispatch import AvatarFleetDispatchDecision
from empire_os.digital_avatar_fleet_recall_launch import (
    prepare_avatar_fleet_recall_launch,
)
from empire_os.meeting_gateway import MeetingPlatform


def runtime(**overrides):
    values = {
        "tenant_id": "tenant-a",
        "avatar_id": "avatar-a",
        "owner_ref": "person:a",
        "owner_name": "Owner A",
        "capability_labels": ("sales",),
        "membership_user_id": "user-1",
        "membership_role": "operator",
        "owner_consent_evidence_ref": "consent:owner:a",
    }
    values.update(overrides)
    return AvatarFleetRuntimeBinding(**values)


def identity(**overrides):
    values = {
        "avatar_id": "avatar-a",
        "owner_name": "Owner A",
        "display_name": "Owner A — AI Digital Avatar",
        "organisation_name": "Empire AI",
        "disclosure_text": "I am Owner A's authorised AI Digital Avatar.",
        "owner_consent_evidence_ref": "consent:owner:a",
    }
    values.update(overrides)
    return DigitalAvatarIdentity(**values)


def dispatch(mode=AvatarMeetingMode.SHADOW, **overrides):
    values = {
        "tenant_id": "tenant-a",
        "meeting_id": "meeting-001",
        "requested_mode": mode.value,
        "selected_avatar_id": "avatar-a",
        "eligible_avatar_ids": ("avatar-a",),
        "available_avatar_ids": ("avatar-a",),
        "assignment_blockers": (),
        "routing_blockers": (),
        "identity_blockers": (),
        "candidate_identity_blockers": {},
        "concurrency_blockers": (),
        "human_selection_required": False,
        "duplicate": False,
        "dispatch_ready": True,
    }
    values.update(overrides)
    return AvatarFleetDispatchDecision(**values)


def prepare(**overrides):
    values = {
        "runtime": runtime(),
        "dispatch": dispatch(),
        "identity": identity(),
        "platform": MeetingPlatform.ZOOM,
        "meeting_url": "https://zoom.us/j/123456789",
        "realtime_webhook_url": "https://empire-ai.co.uk/recall/realtime",
        "recording_consent_evidence_ref": "consent:recording:meeting-001",
        "webhook_verification_evidence_ref": "webhook:verified:v1",
        "account_name": "Example Buyer",
        "objective": "Qualify fit and understand the buyer's needs.",
        "conversation_id": "conversation-001",
        "opportunity_id": "opportunity-001",
        "proof_refs": ("proof:1",),
    }
    values.update(overrides)
    return prepare_avatar_fleet_recall_launch(**values)


def test_valid_shadow_dispatch_builds_canonical_plan_and_manifest():
    result = prepare()
    assert result.launch_ready is True
    assert result.tenant_id == "tenant-a"
    assert result.meeting_id == "meeting-001"
    assert result.avatar_id == "avatar-a"
    assert result.bot_plan.meeting_id == result.session_manifest.session.meeting_id
    assert result.bot_plan.avatar_id == result.session_manifest.session.avatar_id
    assert result.bot_plan.platform == MeetingPlatform.ZOOM
    assert result.session_manifest.session.mode == AvatarMeetingMode.SHADOW
    assert result.session_manifest.session.provider == "recall.ai"
    assert result.session_manifest.conversation_id == "conversation-001"
    assert result.session_manifest.opportunity_id == "opportunity-001"


def test_launch_preserves_visible_ai_identity_and_pending_live_disclosure():
    result = prepare()
    assert "ai" in result.bot_plan.bot_name.lower()
    assert "ai" in result.session_manifest.identity.disclosure_text.lower()
    assert result.ai_disclosure_required is True
    assert result.disclosure_announced is False
    assert result.session_manifest.session.disclosure_announced is False


def test_dispatch_runtime_tenant_or_avatar_mismatch_is_denied():
    with pytest.raises(PermissionError, match="tenant mismatch"):
        prepare(dispatch=dispatch(tenant_id="tenant-b"))
    with pytest.raises(PermissionError, match="avatar mismatch"):
        prepare(dispatch=dispatch(selected_avatar_id="avatar-b"))


def test_identity_owner_or_consent_mismatch_is_denied():
    with pytest.raises(PermissionError, match="owner mismatch"):
        prepare(identity=identity(owner_name="Other Owner"))
    with pytest.raises(PermissionError, match="consent mismatch"):
        prepare(
            identity=identity(
                owner_consent_evidence_ref="consent:other"
            )
        )


@pytest.mark.parametrize(
    "mode",
    [
        AvatarMeetingMode.COPILOT,
        AvatarMeetingMode.REPRESENT,
        AvatarMeetingMode.NEGOTIATE,
        AvatarMeetingMode.CLOSE,
    ],
)
def test_non_shadow_dispatch_is_rejected(mode):
    with pytest.raises(ValueError, match="requires SHADOW mode"):
        prepare(dispatch=dispatch(mode=mode))


def test_dispatch_must_be_ready_and_zero_authority():
    with pytest.raises(ValueError, match="dispatch-ready"):
        prepare(dispatch=dispatch(dispatch_ready=False))
    with pytest.raises(ValueError, match="forbidden execution authority"):
        prepare(
            dispatch=dispatch(provider_call_performed=True)
        )


def test_recording_and_webhook_evidence_are_required():
    with pytest.raises(ValueError, match="recording consent evidence required"):
        prepare(recording_consent_evidence_ref="")
    with pytest.raises(ValueError, match="webhook verification evidence required"):
        prepare(webhook_verification_evidence_ref="")


def test_invalid_urls_are_rejected_by_canonical_bot_plan_builder():
    with pytest.raises(ValueError, match="public HTTPS URL"):
        prepare(meeting_url="http://localhost/meeting")
    with pytest.raises(ValueError, match="public HTTPS URL"):
        prepare(realtime_webhook_url="http://localhost/webhook")


def test_bot_name_must_visibly_identify_ai():
    with pytest.raises(ValueError, match="visibly identify the AI"):
        prepare(
            identity=identity(
                display_name="Owner A Representative"
            )
        )


def test_launch_preparation_never_calls_provider_or_persists_session():
    result = prepare()
    assert result.recommendation_only is True
    assert result.session_persisted is False
    assert result.provider_call_performed is False
    assert result.bot_created is False
    assert result.meeting_join_performed is False
    assert result.output_media_start_performed is False
    assert result.speech_execution_allowed is False
    assert result.commercial_execution_allowed is False
    assert result.payment_execution_allowed is False
    assert result.revenue_recognition_allowed is False
    assert result.execution_authority == "none"
    assert result.bot_plan.api_call_allowed is False
    assert result.bot_plan.live_join_execution is False


def test_runtime_authority_violation_fails_closed():
    with pytest.raises(ValueError, match="forbidden authority"):
        prepare(
            runtime=replace(
                runtime(),
                speech_execution_allowed=True,
            )
        )
