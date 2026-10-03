import json
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from empire_os.digital_avatar import AvatarMeetingMode, DigitalAvatarIdentity
from empire_os.digital_avatar_fleet import AvatarFleetRuntimeBinding
from empire_os.digital_avatar_fleet_dispatch import AvatarFleetDispatchDecision
from empire_os.digital_avatar_fleet_recall_activation import (
    prepare_avatar_fleet_recall_activation,
)
from empire_os.digital_avatar_fleet_recall_execution import (
    execute_avatar_fleet_recall_activation,
)
from empire_os.digital_avatar_fleet_recall_launch import (
    prepare_avatar_fleet_recall_launch,
)
from empire_os.digital_avatar_fleet_recall_materialization import (
    materialize_avatar_fleet_recall_activation,
)
from empire_os.meeting_gateway import MeetingPlatform
from empire_os.recall_shadow_join import RecallShadowJoinApproval


NOW = datetime(2026, 10, 2, 21, 30, tzinfo=timezone.utc)


class FakeTransport:
    def __init__(self, result=(201, {}, {"id": "bot-fleet-live-1"}), exc=None):
        self.result = result
        self.exc = exc
        self.calls = []

    def post_json(self, **kwargs):
        self.calls.append(kwargs)
        if self.exc is not None:
            raise self.exc
        return self.result


def runtime():
    return AvatarFleetRuntimeBinding(
        tenant_id="tenant-a",
        avatar_id="avatar-a",
        owner_ref="person:a",
        owner_name="Owner A",
        capability_labels=("sales",),
        membership_user_id="user-1",
        membership_role="operator",
        owner_consent_evidence_ref="consent:avatar-a",
    )


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


def preparation(tmp_path=None):
    rt = runtime()
    identity = DigitalAvatarIdentity(
        avatar_id="avatar-a",
        owner_name="Owner A",
        display_name="Owner A — AI Digital Avatar",
        organisation_name="Empire AI",
        disclosure_text="I am Owner A's authorised AI Digital Avatar.",
        owner_consent_evidence_ref="consent:avatar-a",
    )
    launch = prepare_avatar_fleet_recall_launch(
        runtime=rt,
        dispatch=dispatch(),
        identity=identity,
        platform=MeetingPlatform.ZOOM,
        meeting_url="https://zoom.us/j/123456789",
        realtime_webhook_url=(
            "https://empire-ai.co.uk/v1/providers/recall/realtime"
        ),
        recording_consent_evidence_ref="consent:recording:meeting-001",
        webhook_verification_evidence_ref="webhook:recall:v1",
        account_name="Example Buyer",
        objective="Qualify fit.",
        join_at="2026-10-02T22:00:00+00:00",
    )
    approval = RecallShadowJoinApproval(
        meeting_id="meeting-001",
        approved_by="Owner A",
        approval_evidence_ref="approval:tenant-a:meeting-001:v1",
        approved_at="2026-10-02T21:00:00+00:00",
        expires_at="2026-10-02T22:30:00+00:00",
        allow_adhoc=False,
    )
    return prepare_avatar_fleet_recall_activation(
        runtime=rt,
        launch=launch,
        approval=approval,
        region="eu-central-1",
        now="2026-10-02T21:30:00+00:00",
    )


def materialized(tmp_path):
    prep = preparation()
    mat = materialize_avatar_fleet_recall_activation(
        preparation=prep,
        session_base_root=tmp_path / "sessions",
        activation_base_root=tmp_path / "activations",
    )
    return prep, mat


def test_default_off_gate_blocks_before_provider_call(tmp_path):
    prep, mat = materialized(tmp_path)
    transport = FakeTransport()
    with pytest.raises(PermissionError, match="explicit live Recall execution"):
        execute_avatar_fleet_recall_activation(
            preparation=prep,
            materialization=mat,
            api_key="test-key",
            transport=transport,
            now=NOW,
        )
    assert transport.calls == []


def test_valid_scoped_activation_executes_exactly_once_with_fake_transport(tmp_path):
    prep, mat = materialized(tmp_path)
    transport = FakeTransport()
    result = execute_avatar_fleet_recall_activation(
        preparation=prep,
        materialization=mat,
        api_key="test-key",
        live_execution_requested=True,
        transport=transport,
        now=NOW,
    )
    assert result.bot_id == "bot-fleet-live-1"
    assert result.provider_status == 201
    assert result.execution_state == "completed"
    assert result.provider_call_performed is True
    assert result.meeting_join_performed is True
    assert result.speech_execution is False
    assert result.chat_send_execution is False
    assert result.commercial_execution is False
    assert result.payment_execution is False
    assert result.revenue_recognition is False
    assert len(transport.calls) == 1

    record = json.loads(
        (
            tmp_path
            / "activations"
            / mat.tenant_scope_key
            / "meeting-001.json"
        ).read_text()
    )
    assert record["execution_state"] == "completed"
    assert record["provider_api_call_performed"] is True
    assert record["live_join_performed"] is True


def test_replay_is_blocked_without_second_provider_call(tmp_path):
    prep, mat = materialized(tmp_path)
    transport = FakeTransport()
    execute_avatar_fleet_recall_activation(
        preparation=prep,
        materialization=mat,
        api_key="test-key",
        live_execution_requested=True,
        transport=transport,
        now=NOW,
    )
    with pytest.raises(ValueError, match="not executable from prepared state"):
        execute_avatar_fleet_recall_activation(
            preparation=prep,
            materialization=mat,
            api_key="test-key",
            live_execution_requested=True,
            transport=transport,
            now=NOW,
        )
    assert len(transport.calls) == 1


def test_scope_or_fingerprint_mismatch_blocks_before_transport(tmp_path):
    prep, mat = materialized(tmp_path)
    transport = FakeTransport()

    with pytest.raises(ValueError, match="tenant scope mismatch"):
        execute_avatar_fleet_recall_activation(
            preparation=prep,
            materialization=replace(
                mat,
                tenant_scope_key="tenant-forged",
            ),
            api_key="test-key",
            live_execution_requested=True,
            transport=transport,
            now=NOW,
        )

    with pytest.raises(ValueError, match="activation fingerprint mismatch"):
        execute_avatar_fleet_recall_activation(
            preparation=prep,
            materialization=replace(
                mat,
                activation_plan_sha256="f" * 64,
            ),
            api_key="test-key",
            live_execution_requested=True,
            transport=transport,
            now=NOW,
        )
    assert transport.calls == []


def test_expired_approval_is_rechecked_before_fake_transport(tmp_path):
    prep, mat = materialized(tmp_path)
    transport = FakeTransport()
    with pytest.raises(ValueError, match="approval not active"):
        execute_avatar_fleet_recall_activation(
            preparation=prep,
            materialization=mat,
            api_key="test-key",
            live_execution_requested=True,
            transport=transport,
            now=datetime(2026, 10, 2, 22, 31, tzinfo=timezone.utc),
        )
    assert transport.calls == []


def test_ambiguous_failure_requires_reconciliation_and_no_blind_retry(tmp_path):
    prep, mat = materialized(tmp_path)
    transport = FakeTransport(exc=TimeoutError("unknown provider outcome"))
    with pytest.raises(TimeoutError):
        execute_avatar_fleet_recall_activation(
            preparation=prep,
            materialization=mat,
            api_key="test-key",
            live_execution_requested=True,
            transport=transport,
            now=NOW,
        )
    assert len(transport.calls) == 1

    record = json.loads(
        (
            tmp_path
            / "activations"
            / mat.tenant_scope_key
            / "meeting-001.json"
        ).read_text()
    )
    assert record["execution_state"] == "reconciliation_required"
    assert record["provider_api_call_performed"] is True
    assert record["live_join_performed"] is False
