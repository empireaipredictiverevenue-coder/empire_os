from datetime import datetime, timezone

import pytest

from empire_os.recall_shadow_bot_client import (
    RecallShadowJoinAuthorization,
    create_recall_shadow_bot,
)
from empire_os.recall_shadow_bot_plan import build_recall_shadow_bot_plan


NOW = datetime(2026, 10, 2, 18, 0, tzinfo=timezone.utc)


def plan(join_at="2026-10-02T19:00:00+00:00"):
    return build_recall_shadow_bot_plan(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        platform="zoom",
        bot_name="Phil — Empire AI Digital Avatar",
        meeting_url="https://zoom.us/j/123456789",
        realtime_webhook_url=(
            "https://empire-ai.co.uk/v1/providers/recall/realtime"
        ),
        recording_consent_evidence_ref="consent:meeting:001",
        webhook_verification_evidence_ref="config:recall-signing:v1",
        join_at=join_at,
    )


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post_json(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def test_scheduled_shadow_bot_create_uses_governed_contract():
    transport = FakeTransport([
        (201, {}, {"id": "bot-live-1"}),
    ])
    result = create_recall_shadow_bot(
        plan=plan(),
        region="eu-central-1",
        api_key="test-key",
        authorization=RecallShadowJoinAuthorization(
            approval_evidence_ref="approval:shadow:1",
        ),
        transport=transport,
        now=NOW,
    )
    assert result.bot_id == "bot-live-1"
    assert result.scheduled is True
    assert result.meeting_join_requested is True
    assert result.speech_execution is False
    assert result.chat_execution is False
    assert result.commercial_execution is False
    assert result.execution_authority == "shadow_join_only"
    call = transport.calls[0]
    assert call["url"] == "https://eu-central-1.recall.ai/api/v1/bot/"
    assert call["headers"]["Authorization"] == "Token test-key"
    assert call["payload"]["metadata"]["empire_mode"] == "shadow"


def test_missing_join_approval_is_rejected_before_transport():
    transport = FakeTransport([])
    with pytest.raises(ValueError, match="explicit shadow join approval"):
        create_recall_shadow_bot(
            plan=plan(),
            region="eu-central-1",
            api_key="test-key",
            authorization=RecallShadowJoinAuthorization(
                approval_evidence_ref="",
            ),
            transport=transport,
            now=NOW,
        )
    assert transport.calls == []


def test_adhoc_join_requires_explicit_allow_adhoc():
    transport = FakeTransport([])
    with pytest.raises(ValueError, match="explicit allow_adhoc"):
        create_recall_shadow_bot(
            plan=plan(join_at=None),
            region="eu-central-1",
            api_key="test-key",
            authorization=RecallShadowJoinAuthorization(
                approval_evidence_ref="approval:shadow:2",
            ),
            transport=transport,
            now=NOW,
        )
    assert transport.calls == []


def test_507_uses_retry_after_and_retries():
    transport = FakeTransport([
        (507, {"Retry-After": "1.5"}, {}),
        (201, {}, {"id": "bot-live-2"}),
    ])
    sleeps = []
    result = create_recall_shadow_bot(
        plan=plan(join_at=None),
        region="eu-central-1",
        api_key="test-key",
        authorization=RecallShadowJoinAuthorization(
            approval_evidence_ref="approval:shadow:3",
            allow_adhoc=True,
        ),
        transport=transport,
        sleeper=sleeps.append,
        now=NOW,
    )
    assert result.bot_id == "bot-live-2"
    assert result.scheduled is False
    assert result.attempts == 2
    assert sleeps == [1.5]


def test_507_defaults_to_thirty_seconds_when_header_missing():
    transport = FakeTransport([
        (507, {}, {}),
        (201, {}, {"id": "bot-live-3"}),
    ])
    sleeps = []
    create_recall_shadow_bot(
        plan=plan(join_at=None),
        region="eu-central-1",
        api_key="test-key",
        authorization=RecallShadowJoinAuthorization(
            approval_evidence_ref="approval:shadow:4",
            allow_adhoc=True,
        ),
        transport=transport,
        sleeper=sleeps.append,
        now=NOW,
    )
    assert sleeps == [30.0]


def test_invalid_region_is_rejected():
    with pytest.raises(ValueError, match="unsupported Recall region"):
        create_recall_shadow_bot(
            plan=plan(),
            region="uk-south-1",
            api_key="test-key",
            authorization=RecallShadowJoinAuthorization(
                approval_evidence_ref="approval:shadow:5",
            ),
            transport=FakeTransport([]),
            now=NOW,
        )


def test_time_bounded_authorization_is_rechecked_at_provider_boundary():
    transport = FakeTransport([])
    authorization = RecallShadowJoinAuthorization(
        approval_evidence_ref="approval:shadow:bounded",
        meeting_id="meeting-001",
        approved_by="Phil Livesley",
        approved_at="2026-10-02T17:00:00+00:00",
        expires_at="2026-10-02T17:30:00+00:00",
    )
    with pytest.raises(ValueError, match="not active"):
        create_recall_shadow_bot(
            plan=plan(),
            region="eu-central-1",
            api_key="test-key",
            authorization=authorization,
            transport=transport,
            now=NOW,
        )
    assert transport.calls == []


def test_meeting_bound_authorization_cannot_be_replayed_to_other_plan():
    transport = FakeTransport([])
    authorization = RecallShadowJoinAuthorization(
        approval_evidence_ref="approval:shadow:meeting-999",
        meeting_id="meeting-999",
        approved_by="Phil Livesley",
        approved_at="2026-10-02T17:30:00+00:00",
        expires_at="2026-10-02T19:30:00+00:00",
    )
    with pytest.raises(ValueError, match="meeting mismatch"):
        create_recall_shadow_bot(
            plan=plan(),
            region="eu-central-1",
            api_key="test-key",
            authorization=authorization,
            transport=transport,
            now=NOW,
        )
    assert transport.calls == []


def test_time_bounded_approval_is_rechecked_at_provider_call():
    transport = FakeTransport([])
    authorization = RecallShadowJoinAuthorization(
        approval_evidence_ref="approval:shadow:expired",
        meeting_id="meeting-001",
        approved_by="Phil Livesley",
        approved_at="2026-10-02T18:00:00+00:00",
        expires_at="2026-10-02T18:30:00+00:00",
    )
    with pytest.raises(ValueError, match="approval not active"):
        create_recall_shadow_bot(
            plan=plan(),
            region="eu-central-1",
            api_key="test-key",
            authorization=authorization,
            transport=transport,
            now=datetime(2026, 10, 2, 18, 31, tzinfo=timezone.utc),
        )
    assert transport.calls == []
