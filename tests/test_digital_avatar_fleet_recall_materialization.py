from pathlib import Path

import pytest

from empire_os.digital_avatar import AvatarMeetingMode, DigitalAvatarIdentity
from empire_os.digital_avatar_fleet import AvatarFleetRuntimeBinding
from empire_os.digital_avatar_fleet_dispatch import AvatarFleetDispatchDecision
from empire_os.digital_avatar_fleet_recall_activation import (
    prepare_avatar_fleet_recall_activation,
)
from empire_os.digital_avatar_fleet_recall_launch import (
    prepare_avatar_fleet_recall_launch,
)
from empire_os.digital_avatar_fleet_recall_materialization import (
    materialize_avatar_fleet_recall_activation,
    tenant_scope_key,
)
from empire_os.meeting_gateway import MeetingPlatform
from empire_os.recall_shadow_join import RecallShadowJoinApproval


NOW = "2026-10-02T21:30:00+00:00"


def runtime(tenant="tenant-a", avatar="avatar-a", owner="Owner A"):
    return AvatarFleetRuntimeBinding(
        tenant_id=tenant,
        avatar_id=avatar,
        owner_ref=f"person:{avatar}",
        owner_name=owner,
        capability_labels=("sales",),
        membership_user_id=f"user:{tenant}",
        membership_role="operator",
        owner_consent_evidence_ref=f"consent:{avatar}",
    )


def identity(avatar="avatar-a", owner="Owner A"):
    return DigitalAvatarIdentity(
        avatar_id=avatar,
        owner_name=owner,
        display_name=f"{owner} — AI Digital Avatar",
        organisation_name="Empire AI",
        disclosure_text=f"I am {owner}'s authorised AI Digital Avatar.",
        owner_consent_evidence_ref=f"consent:{avatar}",
    )


def dispatch(tenant="tenant-a", avatar="avatar-a"):
    return AvatarFleetDispatchDecision(
        tenant_id=tenant,
        meeting_id="meeting-001",
        requested_mode=AvatarMeetingMode.SHADOW.value,
        selected_avatar_id=avatar,
        eligible_avatar_ids=(avatar,),
        available_avatar_ids=(avatar,),
        assignment_blockers=(),
        routing_blockers=(),
        identity_blockers=(),
        candidate_identity_blockers={},
        concurrency_blockers=(),
        human_selection_required=False,
        duplicate=False,
        dispatch_ready=True,
    )


def activation_preparation(
    tenant="tenant-a",
    avatar="avatar-a",
    owner="Owner A",
    *,
    region="eu-central-1",
    approval_ref=None,
):
    rt = runtime(tenant, avatar, owner)
    ident = identity(avatar, owner)
    launch = prepare_avatar_fleet_recall_launch(
        runtime=rt,
        dispatch=dispatch(tenant, avatar),
        identity=ident,
        platform=MeetingPlatform.ZOOM,
        meeting_url="https://zoom.us/j/123456789",
        realtime_webhook_url=(
            "https://empire-ai.co.uk/v1/providers/recall/realtime"
        ),
        recording_consent_evidence_ref="consent:recording:meeting-001",
        webhook_verification_evidence_ref="webhook:recall-signing:v1",
        account_name="Example Buyer",
        objective="Qualify fit.",
    )
    approval = RecallShadowJoinApproval(
        meeting_id="meeting-001",
        approved_by=owner,
        approval_evidence_ref=(
            approval_ref or f"approval:{tenant}:meeting-001:v1"
        ),
        approved_at="2026-10-02T21:00:00+00:00",
        expires_at="2026-10-02T22:00:00+00:00",
        allow_adhoc=True,
    )
    return prepare_avatar_fleet_recall_activation(
        runtime=rt,
        launch=launch,
        approval=approval,
        region=region,
        now=NOW,
    )


def test_exact_same_tenant_packet_materializes_idempotently(tmp_path):
    prep = activation_preparation()
    first = materialize_avatar_fleet_recall_activation(
        preparation=prep,
        session_base_root=tmp_path / "sessions",
        activation_base_root=tmp_path / "activations",
    )
    second = materialize_avatar_fleet_recall_activation(
        preparation=prep,
        session_base_root=tmp_path / "sessions",
        activation_base_root=tmp_path / "activations",
    )
    assert first.activation_plan_sha256 == second.activation_plan_sha256
    assert first.activation_record == second.activation_record
    assert first.activation_persisted is True
    assert first.session_persisted is True


def test_two_tenants_same_meeting_id_get_distinct_scope_roots(tmp_path):
    first = materialize_avatar_fleet_recall_activation(
        preparation=activation_preparation(
            "tenant-a", "avatar-a", "Owner A"
        ),
        session_base_root=tmp_path / "sessions",
        activation_base_root=tmp_path / "activations",
    )
    second = materialize_avatar_fleet_recall_activation(
        preparation=activation_preparation(
            "tenant-b", "avatar-b", "Owner B"
        ),
        session_base_root=tmp_path / "sessions",
        activation_base_root=tmp_path / "activations",
    )
    assert first.meeting_id == second.meeting_id == "meeting-001"
    assert first.tenant_scope_key != second.tenant_scope_key
    assert first.session_root != second.session_root
    assert first.activation_root != second.activation_root
    assert Path(first.activation_root, "meeting-001.json").is_file()
    assert Path(second.activation_root, "meeting-001.json").is_file()


def test_same_tenant_same_meeting_conflicting_activation_fails_closed(tmp_path):
    first = activation_preparation(
        region="eu-central-1",
        approval_ref="approval:tenant-a:meeting-001:v1",
    )
    second = activation_preparation(
        region="us-east-1",
        approval_ref="approval:tenant-a:meeting-001:v2",
    )
    materialize_avatar_fleet_recall_activation(
        preparation=first,
        session_base_root=tmp_path / "sessions",
        activation_base_root=tmp_path / "activations",
    )
    with pytest.raises(ValueError, match="activation record conflict"):
        materialize_avatar_fleet_recall_activation(
            preparation=second,
            session_base_root=tmp_path / "sessions",
            activation_base_root=tmp_path / "activations",
        )


def test_scope_key_is_hash_based_and_path_safe():
    scope = tenant_scope_key("../../tenant/a")
    assert scope.startswith("tenant-")
    assert "/" not in scope
    assert "\\" not in scope
    assert ".." not in scope
    assert "tenant/a" not in scope


def test_files_are_created_only_inside_tenant_scoped_roots(tmp_path):
    value = materialize_avatar_fleet_recall_activation(
        preparation=activation_preparation(),
        session_base_root=tmp_path / "sessions",
        activation_base_root=tmp_path / "activations",
    )
    assert Path(value.session_root, "meeting-001.json").is_file()
    assert Path(value.activation_root, "meeting-001.json").is_file()
    assert not Path(tmp_path / "sessions" / "meeting-001.json").exists()
    assert not Path(tmp_path / "activations" / "meeting-001.json").exists()


def test_materialization_never_calls_provider_or_joins(tmp_path):
    value = materialize_avatar_fleet_recall_activation(
        preparation=activation_preparation(),
        session_base_root=tmp_path / "sessions",
        activation_base_root=tmp_path / "activations",
    )
    record = value.activation_record
    assert value.provider_call_performed is False
    assert value.meeting_join_performed is False
    assert value.speech_execution is False
    assert value.chat_send_execution is False
    assert value.commercial_execution is False
    assert value.payment_execution is False
    assert value.revenue_recognition is False
    assert value.execution_authority == "none"
    assert record.provider_api_call_started is False
    assert record.provider_api_call_performed is False
    assert record.live_join_performed is False
    assert record.execution_state == "prepared"
