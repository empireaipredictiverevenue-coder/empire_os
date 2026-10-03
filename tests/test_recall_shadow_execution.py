import json
from datetime import datetime, timezone

import pytest

from empire_os.digital_avatar import DigitalAvatarIdentity
from empire_os.recall_shadow_activation import prepare_recall_shadow_activation
from empire_os.recall_shadow_activation_store import (
    materialize_recall_shadow_activation,
)
from empire_os.recall_shadow_execution import (
    execute_materialized_recall_shadow_activation,
    validate_materialized_shadow_execution,
)
from empire_os.recall_shadow_join import RecallShadowJoinApproval


NOW = datetime(2026, 10, 2, 18, 30, tzinfo=timezone.utc)


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
        join_at="2026-10-02T19:00:00+00:00",
    )


class FakeTransport:
    def __init__(self, result=(201, {}, {"id": "bot-live-1"}), exc=None):
        self.result = result
        self.exc = exc
        self.calls = []

    def post_json(self, **kwargs):
        self.calls.append(kwargs)
        if self.exc is not None:
            raise self.exc
        return self.result


def materialized(tmp_path, value=None):
    value = value or packet()
    materialize_recall_shadow_activation(
        packet=value,
        session_root=tmp_path / "sessions",
        activation_root=tmp_path / "activations",
    )
    return value


def test_materialized_execution_completes_once_and_records_bot(tmp_path):
    value = materialized(tmp_path)
    transport = FakeTransport()
    result = execute_materialized_recall_shadow_activation(
        packet=value,
        activation_root=tmp_path / "activations",
        api_key="test-key",
        transport=transport,
        now=NOW,
    )
    assert result["bot_id"] == "bot-live-1"
    assert result["execution_state"] == "completed"
    assert result["deduplication_enforced"] is True
    assert len(transport.calls) == 1

    record = json.loads(
        (tmp_path / "activations" / "meeting-001.json").read_text()
    )
    assert record["execution_state"] == "completed"
    assert record["provider_api_call_started"] is True
    assert record["provider_api_call_performed"] is True
    assert record["live_join_performed"] is True
    assert record["provider_bot_id"] == "bot-live-1"
    assert record["provider_status"] == 201

    with pytest.raises(ValueError, match="not executable from prepared state"):
        execute_materialized_recall_shadow_activation(
            packet=value,
            activation_root=tmp_path / "activations",
            api_key="test-key",
            transport=transport,
            now=NOW,
        )
    assert len(transport.calls) == 1


def test_plan_drift_is_blocked_before_provider_call(tmp_path):
    materialized(tmp_path, packet(objective="qualify fit"))
    changed = packet(objective="different objective")
    transport = FakeTransport()
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        execute_materialized_recall_shadow_activation(
            packet=changed,
            activation_root=tmp_path / "activations",
            api_key="test-key",
            transport=transport,
            now=NOW,
        )
    assert transport.calls == []


def test_ambiguous_provider_failure_requires_reconciliation_not_retry(tmp_path):
    value = materialized(tmp_path)
    transport = FakeTransport(exc=TimeoutError("network outcome unknown"))
    with pytest.raises(TimeoutError):
        execute_materialized_recall_shadow_activation(
            packet=value,
            activation_root=tmp_path / "activations",
            api_key="test-key",
            transport=transport,
            now=NOW,
        )
    assert len(transport.calls) == 1

    record = json.loads(
        (tmp_path / "activations" / "meeting-001.json").read_text()
    )
    assert record["execution_state"] == "reconciliation_required"
    assert record["provider_api_call_started"] is True
    assert record["provider_api_call_performed"] is True
    assert record["live_join_performed"] is False

    with pytest.raises(ValueError, match="not executable from prepared state"):
        execute_materialized_recall_shadow_activation(
            packet=value,
            activation_root=tmp_path / "activations",
            api_key="test-key",
            transport=FakeTransport(),
            now=NOW,
        )


def test_validate_requires_materialized_record(tmp_path):
    with pytest.raises(ValueError, match="activation record missing"):
        validate_materialized_shadow_execution(
            packet=packet(),
            activation_root=tmp_path / "activations",
        )
