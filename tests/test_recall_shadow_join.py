import pytest

from empire_os.recall_shadow_bot_plan import build_recall_shadow_bot_plan
from empire_os.recall_shadow_join import (
    RecallShadowJoinApproval,
    execute_recall_shadow_join,
    prepare_recall_shadow_join,
)


def plan():
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
        join_at="2026-10-02T19:00:00+00:00",
    )


def approval():
    return RecallShadowJoinApproval(
        meeting_id="meeting-001",
        approved_by="Phil Livesley",
        approval_evidence_ref="approval:recall-shadow:meeting-001:v1",
        approved_at="2026-10-02T18:00:00+00:00",
        expires_at="2026-10-02T20:00:00+00:00",
    )


def test_prepare_join_grants_meeting_join_only():
    request = prepare_recall_shadow_join(
        plan=plan(),
        approval=approval(),
        region="eu-central-1",
        now="2026-10-02T18:30:00+00:00",
    )
    assert request.live_join_authorized is True
    assert request.speech_execution is False
    assert request.chat_send_execution is False
    assert request.commercial_execution is False
    assert request.execution_authority == "shadow_join_only"
    assert request.endpoint == (
        "https://eu-central-1.recall.ai/api/v1/bot/"
    )


def test_expired_approval_is_rejected():
    with pytest.raises(ValueError, match="not active"):
        prepare_recall_shadow_join(
            plan=plan(),
            approval=approval(),
            region="eu-central-1",
            now="2026-10-02T20:00:00+00:00",
        )


def test_wrong_meeting_approval_is_rejected():
    item = approval()
    object.__setattr__(item, "meeting_id", "meeting-999")
    with pytest.raises(ValueError, match="meeting mismatch"):
        prepare_recall_shadow_join(
            plan=plan(),
            approval=item,
            region="eu-central-1",
            now="2026-10-02T18:30:00+00:00",
        )


class FakeTransport:
    def __init__(self):
        self.calls = []

    def post_json(self, *, url, headers, payload, timeout_s):
        self.calls.append(
            (url, dict(headers), dict(payload), timeout_s)
        )
        return 201, {}, {"id": "bot-live-test-123"}


def test_execute_join_uses_authorized_request_but_no_output_authority():
    request = prepare_recall_shadow_join(
        plan=plan(),
        approval=approval(),
        region="eu-central-1",
        now="2026-10-02T18:30:00+00:00",
    )
    transport = FakeTransport()
    result = execute_recall_shadow_join(
        request=request,
        api_key="test-api-key",
        transport=transport,
        now=__import__("datetime").datetime(
            2026, 10, 2, 18, 30,
            tzinfo=__import__("datetime").timezone.utc,
        ),
    )
    assert result["bot_id"] == "bot-live-test-123"
    assert result["live_join_performed"] is True
    assert result["speech_execution"] is False
    assert result["chat_send_execution"] is False
    assert result["commercial_execution"] is False
    assert result["execution_authority"] == "shadow_join_only"
    assert len(transport.calls) == 1
    _, headers, body, timeout_s = transport.calls[0]
    assert headers["Authorization"] == "Token test-api-key"
    assert body["metadata"]["empire_meeting_id"] == "meeting-001"
    assert body["metadata"]["execution_authority"] == "none"
    assert timeout_s == 20.0


def test_execute_requires_api_key():
    request = prepare_recall_shadow_join(
        plan=plan(),
        approval=approval(),
        region="eu-central-1",
        now="2026-10-02T18:30:00+00:00",
    )
    with pytest.raises(ValueError, match="API key required"):
        execute_recall_shadow_join(
            request=request,
            api_key="",
            transport=FakeTransport(),
            now=__import__("datetime").datetime(
                2026, 10, 2, 18, 30,
                tzinfo=__import__("datetime").timezone.utc,
            ),
        )
