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
)
from empire_os.recall_shadow_join import RecallShadowJoinApproval
from empire_os.recall_shadow_reconciliation import (
    reconcile_recall_shadow_activation,
)


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


class TimeoutCreateTransport:
    def __init__(self):
        self.calls = []

    def post_json(self, **kwargs):
        self.calls.append(kwargs)
        raise TimeoutError("outcome unknown")


class FakeLookupTransport:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def get_json(self, **kwargs):
        self.calls.append(kwargs)
        return 200, {}, {"count": len(self.results), "results": self.results}


def bot(bot_id="bot-live-1", meeting_id="meeting-001", avatar_id="avatar-phil-v1"):
    return {
        "id": bot_id,
        "metadata": {
            "empire_meeting_id": meeting_id,
            "empire_avatar_id": avatar_id,
            "empire_mode": "shadow",
            "execution_authority": "none",
        },
    }


def ambiguous_activation(tmp_path):
    value = packet()
    materialize_recall_shadow_activation(
        packet=value,
        session_root=tmp_path / "sessions",
        activation_root=tmp_path / "activations",
    )
    with pytest.raises(TimeoutError):
        execute_materialized_recall_shadow_activation(
            packet=value,
            activation_root=tmp_path / "activations",
            api_key="test-key",
            transport=TimeoutCreateTransport(),
            now=NOW,
        )
    return value


def test_reconciliation_finds_exact_bot_and_completes_record(tmp_path):
    value = ambiguous_activation(tmp_path)
    lookup = FakeLookupTransport([bot()])
    result = reconcile_recall_shadow_activation(
        packet=value,
        activation_root=tmp_path / "activations",
        api_key="test-key",
        transport=lookup,
    )
    assert result["resolution"] == "bot_found"
    assert result["bot_id"] == "bot-live-1"
    assert result["match_count"] == 1
    assert result["deduplication_enforced"] is True
    assert result["provider_api_call_performed"] is False
    assert len(lookup.calls) == 1
    assert "metadata__empire_meeting_id=meeting-001" in lookup.calls[0]["url"]
    assert "metadata__empire_avatar_id=avatar-phil-v1" in lookup.calls[0]["url"]
    assert "metadata__empire_mode=shadow" in lookup.calls[0]["url"]
    assert "metadata__execution_authority=none" in lookup.calls[0]["url"]

    record = json.loads(
        (tmp_path / "activations" / "meeting-001.json").read_text()
    )
    assert record["execution_state"] == "completed_reconciled"
    assert record["provider_bot_id"] == "bot-live-1"
    assert record["live_join_performed"] is True


def test_reconciliation_no_bot_found_stays_fail_closed(tmp_path):
    value = ambiguous_activation(tmp_path)
    result = reconcile_recall_shadow_activation(
        packet=value,
        activation_root=tmp_path / "activations",
        api_key="test-key",
        transport=FakeLookupTransport([]),
    )
    assert result["resolution"] == "no_bot_found"
    assert result["execution_state"] == "reconciliation_no_bot_found"
    record = json.loads(
        (tmp_path / "activations" / "meeting-001.json").read_text()
    )
    assert record["live_join_performed"] is False


def test_reconciliation_multiple_bots_is_conflict(tmp_path):
    value = ambiguous_activation(tmp_path)
    result = reconcile_recall_shadow_activation(
        packet=value,
        activation_root=tmp_path / "activations",
        api_key="test-key",
        transport=FakeLookupTransport([
            bot("bot-1"),
            bot("bot-2"),
        ]),
    )
    assert result["resolution"] == "multiple_bots_found"
    assert result["match_count"] == 2
    assert result["execution_state"] == "reconciliation_conflict"


def test_reconciliation_rejects_plan_drift_before_lookup(tmp_path):
    ambiguous_activation(tmp_path)
    changed = packet(objective="changed objective")
    lookup = FakeLookupTransport([bot()])
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        reconcile_recall_shadow_activation(
            packet=changed,
            activation_root=tmp_path / "activations",
            api_key="test-key",
            transport=lookup,
        )
    assert lookup.calls == []


def test_reconciliation_requires_ambiguous_state(tmp_path):
    value = packet()
    materialize_recall_shadow_activation(
        packet=value,
        session_root=tmp_path / "sessions",
        activation_root=tmp_path / "activations",
    )
    with pytest.raises(ValueError, match="does not require reconciliation"):
        reconcile_recall_shadow_activation(
            packet=value,
            activation_root=tmp_path / "activations",
            api_key="test-key",
            transport=FakeLookupTransport([bot()]),
        )


def test_reconciliation_ignores_bot_with_wrong_mode_or_authority(tmp_path):
    value = ambiguous_activation(tmp_path)
    unsafe_mode = bot("bot-close")
    unsafe_mode["metadata"]["empire_mode"] = "close"
    unsafe_authority = bot("bot-authority")
    unsafe_authority["metadata"]["execution_authority"] = "live"

    result = reconcile_recall_shadow_activation(
        packet=value,
        activation_root=tmp_path / "activations",
        api_key="test-key",
        transport=FakeLookupTransport([
            unsafe_mode,
            unsafe_authority,
        ]),
    )
    assert result["resolution"] == "no_bot_found"
    assert result["match_count"] == 0
    record = json.loads(
        (tmp_path / "activations" / "meeting-001.json").read_text()
    )
    assert record["live_join_performed"] is False
    assert record["execution_state"] == "reconciliation_no_bot_found"
