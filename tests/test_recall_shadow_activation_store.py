import json

import pytest

from empire_os.digital_avatar import DigitalAvatarIdentity
from empire_os.recall_shadow_activation import prepare_recall_shadow_activation
from empire_os.recall_shadow_activation_store import (
    activation_plan_sha256,
    materialize_recall_shadow_activation,
)
from empire_os.recall_shadow_join import RecallShadowJoinApproval


def packet(*, objective="qualify fit and agree next step"):
    return prepare_recall_shadow_activation(
        identity=DigitalAvatarIdentity(
            avatar_id="avatar-phil-v1",
            owner_name="Phil Livesley",
            display_name="Phil — Empire AI Digital Avatar",
            organisation_name="Empire AI",
            disclosure_text="I am Phil's authorised Empire AI Digital Avatar.",
            owner_consent_evidence_ref="consent:phil:avatar:v1",
        ),
        meeting_id="meeting-001",
        platform="zoom",
        meeting_url="https://zoom.us/j/123456789",
        bot_name="Phil — Empire AI Digital Avatar",
        public_realtime_url=(
            "https://empire-ai.co.uk/v1/providers/recall/realtime"
        ),
        account_name="Example Buyer",
        objective=objective,
        owner_join_approval=RecallShadowJoinApproval(
            meeting_id="meeting-001",
            approved_by="Phil Livesley",
            approval_evidence_ref="approval:shadow:meeting-001:v1",
            approved_at="2026-10-02T18:00:00+00:00",
            expires_at="2026-10-02T20:00:00+00:00",
        ),
        region="eu-central-1",
        now="2026-10-02T18:30:00+00:00",
        recording_consent_evidence_ref="consent:meeting:001",
        webhook_verification_evidence_ref="config:recall-signing:v1",
    )


def test_materialized_activation_is_private_and_nonexecuting(tmp_path):
    value = packet()
    record = materialize_recall_shadow_activation(
        packet=value,
        session_root=tmp_path / "sessions",
        activation_root=tmp_path / "activations",
    )
    assert record.plan_sha256 == activation_plan_sha256(value)
    assert record.live_join_prepared is True
    assert record.live_join_performed is False
    assert record.provider_api_call_performed is False
    assert record.execution_authority == "none"
    assert record.join_execution_authority == "shadow_join_only"

    activation_path = tmp_path / "activations" / "meeting-001.json"
    session_path = tmp_path / "sessions" / "meeting-001.json"
    assert activation_path.is_file()
    assert session_path.is_file()
    assert oct(activation_path.stat().st_mode & 0o777) == "0o600"
    assert oct(session_path.stat().st_mode & 0o777) == "0o600"


def test_same_activation_materialization_is_idempotent(tmp_path):
    value = packet()
    first = materialize_recall_shadow_activation(
        packet=value,
        session_root=tmp_path / "sessions",
        activation_root=tmp_path / "activations",
    )
    second = materialize_recall_shadow_activation(
        packet=value,
        session_root=tmp_path / "sessions",
        activation_root=tmp_path / "activations",
    )
    assert first.plan_sha256 == second.plan_sha256
    assert len(list((tmp_path / "activations").glob("*.json"))) == 1


def test_conflicting_plan_for_same_meeting_fails_closed(tmp_path):
    first = packet(objective="qualify fit")
    materialize_recall_shadow_activation(
        packet=first,
        session_root=tmp_path / "sessions",
        activation_root=tmp_path / "activations",
    )
    second = packet(objective="close immediately")
    with pytest.raises(ValueError, match="activation record conflict"):
        materialize_recall_shadow_activation(
            packet=second,
            session_root=tmp_path / "sessions",
            activation_root=tmp_path / "activations",
        )
    session = json.loads(
        (tmp_path / "sessions" / "meeting-001.json").read_text()
    )
    assert session["objective"] == "qualify fit"


def test_record_does_not_persist_provider_api_key(tmp_path):
    value = packet()
    materialize_recall_shadow_activation(
        packet=value,
        session_root=tmp_path / "sessions",
        activation_root=tmp_path / "activations",
    )
    raw = (
        tmp_path / "activations" / "meeting-001.json"
    ).read_text(encoding="utf-8")
    assert "RECALL_API_KEY" not in raw
    assert "whsec_" not in raw
    parsed = json.loads(raw)
    assert parsed["approval_evidence_ref"] == (
        "approval:shadow:meeting-001:v1"
    )


def test_rematerialization_returns_persisted_execution_truth(tmp_path):
    value = packet()
    materialize_recall_shadow_activation(
        packet=value,
        session_root=tmp_path / "sessions",
        activation_root=tmp_path / "activations",
    )
    path = tmp_path / "activations" / "meeting-001.json"
    persisted = json.loads(path.read_text())
    persisted["execution_state"] = "completed"
    persisted["provider_api_call_started"] = True
    persisted["provider_api_call_performed"] = True
    persisted["live_join_performed"] = True
    persisted["provider_bot_id"] = "bot-live-1"
    persisted["provider_status"] = 201
    path.write_text(json.dumps(persisted))

    record = materialize_recall_shadow_activation(
        packet=value,
        session_root=tmp_path / "sessions",
        activation_root=tmp_path / "activations",
    )
    assert record.execution_state == "completed"
    assert record.live_join_performed is True
    assert record.provider_api_call_performed is True
    assert record.provider_bot_id == "bot-live-1"
    assert record.provider_status == 201
