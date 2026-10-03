from dataclasses import replace

import pytest

from empire_os.digital_avatar import (
    AvatarMeetingMode,
    DigitalAvatarIdentity,
)
from empire_os.digital_avatar_fleet import AvatarFleetRuntimeBinding
from empire_os.digital_avatar_fleet_dispatch import AvatarFleetDispatchDecision
from empire_os.digital_avatar_fleet_recall_activation import (
    prepare_avatar_fleet_recall_activation,
)
from empire_os.digital_avatar_fleet_recall_launch import (
    prepare_avatar_fleet_recall_launch,
)
from empire_os.meeting_gateway import MeetingPlatform
from empire_os.recall_shadow_join import RecallShadowJoinApproval


NOW = "2026-10-02T21:30:00+00:00"


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


def dispatch():
    return AvatarFleetDispatchDecision(
        tenant_id="tenant-a",
        meeting_id="meeting-001",
        requested_mode=AvatarMeetingMode.SHADOW.value,
        selected_avatar_id="avatar-a",
        eligible_avatar_ids=("avatar-a",),
        available_avatar_ids=("avatar-a",),
        assignment_blockers=(),
        routing_blockers=(),
        identity_blockers=(),
        candidate_identity_blockers={},
        concurrency_blockers=(),
        human_selection_required=False,
        duplicate=False,
        dispatch_ready=True,
    )


def launch(**overrides):
    values = {
        "runtime": runtime(),
        "dispatch": dispatch(),
        "identity": identity(),
        "platform": MeetingPlatform.ZOOM,
        "meeting_url": "https://zoom.us/j/123456789",
        "realtime_webhook_url": "https://empire-ai.co.uk/v1/providers/recall/realtime",
        "recording_consent_evidence_ref": "consent:recording:meeting-001",
        "webhook_verification_evidence_ref": "webhook:recall-signing:v1",
        "account_name": "Example Buyer",
        "objective": "Qualify fit and understand requirements.",
    }
    values.update(overrides)
    return prepare_avatar_fleet_recall_launch(**values)


def approval(**overrides):
    values = {
        "meeting_id": "meeting-001",
        "approved_by": "Owner A",
        "approval_evidence_ref": "approval:recall-shadow:meeting-001:v1",
        "approved_at": "2026-10-02T21:00:00+00:00",
        "expires_at": "2026-10-02T22:00:00+00:00",
        "allow_adhoc": True,
    }
    values.update(overrides)
    return RecallShadowJoinApproval(**values)


def prepare(**overrides):
    values = {
        "runtime": runtime(),
        "launch": launch(),
        "approval": approval(),
        "region": "eu-central-1",
        "now": NOW,
    }
    values.update(overrides)
    return prepare_avatar_fleet_recall_activation(**values)


def test_matching_fleet_launch_and_active_owner_approval_are_activation_ready():
    value = prepare()
    assert value.activation_ready is True
    assert value.fleet_scope_verified is True
    assert value.live_join_authorized is True
    assert value.tenant_id == "tenant-a"
    assert value.meeting_id == "meeting-001"
    assert value.avatar_id == "avatar-a"
    assert value.approval_evidence_ref == (
        "approval:recall-shadow:meeting-001:v1"
    )
    assert value.activation_packet.bot_plan is value.activation_packet.join_request.plan
    assert value.activation_packet.bot_plan.meeting_id == value.meeting_id
    assert value.activation_packet.manifest.identity.avatar_id == value.avatar_id


def test_cross_tenant_or_avatar_runtime_mismatch_is_denied():
    with pytest.raises(PermissionError, match="tenant mismatch"):
        prepare(runtime=runtime(tenant_id="tenant-b"))
    with pytest.raises(PermissionError, match="avatar mismatch"):
        prepare(runtime=runtime(avatar_id="avatar-b"))


def test_launch_owner_or_consent_mismatch_is_denied():
    wrong_owner_launch = launch(
        runtime=runtime(owner_name="Other Owner"),
        identity=identity(owner_name="Other Owner"),
    )
    with pytest.raises(PermissionError, match="owner mismatch"):
        prepare(launch=wrong_owner_launch)

    wrong_consent_launch = launch(
        runtime=runtime(
            owner_consent_evidence_ref="consent:other"
        ),
        identity=identity(
            owner_consent_evidence_ref="consent:other"
        ),
    )
    with pytest.raises(PermissionError, match="consent mismatch"):
        prepare(launch=wrong_consent_launch)


def test_approval_owner_must_match_runtime_owner():
    with pytest.raises(PermissionError, match="approval owner mismatch"):
        prepare(approval=approval(approved_by="Other Owner"))


def test_wrong_or_expired_approval_is_denied():
    with pytest.raises(ValueError, match="approval meeting mismatch"):
        prepare(approval=approval(meeting_id="meeting-999"))

    with pytest.raises(ValueError, match="approval not active"):
        prepare(
            approval=approval(
                approved_at="2026-10-02T19:00:00+00:00",
                expires_at="2026-10-02T20:00:00+00:00",
            )
        )


def test_canonical_region_validation_is_preserved():
    with pytest.raises(ValueError, match="unsupported Recall region"):
        prepare(region="moon-1")


def test_launch_execution_state_blocks_activation_preparation():
    base = launch()
    with pytest.raises(ValueError, match="forbidden execution state"):
        prepare(
            launch=replace(
                base,
                provider_call_performed=True,
            )
        )


def test_activation_wrapper_never_materializes_or_calls_provider():
    value = prepare()
    assert value.activation_persisted is False
    assert value.provider_call_performed is False
    assert value.bot_created is False
    assert value.meeting_join_performed is False
    assert value.speech_execution is False
    assert value.chat_send_execution is False
    assert value.commercial_execution is False
    assert value.payment_execution is False
    assert value.revenue_recognition is False
    assert value.execution_authority == "shadow_join_only_pending_execution"
    assert value.activation_packet.live_join_performed is False
    assert value.activation_packet.speech_execution is False
    assert value.activation_packet.chat_send_execution is False
    assert value.activation_packet.commercial_execution is False
