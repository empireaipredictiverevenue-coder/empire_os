import pytest

from empire_os.recall_shadow_bot_plan import build_recall_shadow_bot_plan


def build(**overrides):
    values = {
        "meeting_id": "meeting-001",
        "avatar_id": "avatar-phil-v1",
        "platform": "zoom",
        "bot_name": "Phil — Empire AI Digital Avatar",
        "meeting_url": "https://zoom.us/j/123456789",
        "realtime_webhook_url": (
            "https://empire-ai.co.uk/v1/providers/recall/realtime"
        ),
        "recording_consent_evidence_ref": "consent:meeting:001",
        "webhook_verification_evidence_ref": "config:recall-signing:v1",
        "join_at": "2026-10-03T10:00:00+01:00",
    }
    values.update(overrides)
    return build_recall_shadow_bot_plan(**values)


def test_shadow_bot_plan_is_non_executing_and_disclosed():
    plan = build()
    assert plan.mode == "SHADOW"
    assert plan.api_call_allowed is False
    assert plan.live_join_execution is False
    assert plan.output_media_enabled is False
    assert plan.chat_send_enabled is False
    assert plan.speech_execution is False
    assert plan.execution_authority == "none"
    assert plan.request_body["bot_name"] == "Phil — Empire AI Digital Avatar"
    assert plan.request_body["join_at"] == "2026-10-03T10:00:00+01:00"
    metadata = plan.request_body["metadata"]
    assert metadata["empire_meeting_id"] == "meeting-001"
    assert metadata["empire_avatar_id"] == "avatar-phil-v1"
    assert metadata["empire_platform"] == "zoom"


def test_plan_requests_low_latency_final_transcript_and_participant_events():
    body = build().request_body
    provider = body["recording_config"]["transcript"]["provider"]
    assert provider["recallai_streaming"]["mode"] == "prioritize_low_latency"
    endpoints = body["recording_config"]["realtime_endpoints"]
    assert endpoints[0]["type"] == "webhook"
    assert "transcript.data" in endpoints[0]["events"]
    assert "transcript.partial_data" not in endpoints[0]["events"]
    assert "participant_events.join" in endpoints[0]["events"]
    assert "participant_events.chat_message" in endpoints[0]["events"]


def test_plan_requires_recording_consent_evidence():
    with pytest.raises(ValueError, match="recording consent evidence"):
        build(recording_consent_evidence_ref="")


def test_plan_requires_webhook_verification_evidence():
    with pytest.raises(ValueError, match="webhook verification evidence"):
        build(webhook_verification_evidence_ref="")


def test_plan_rejects_hidden_ai_identity():
    with pytest.raises(ValueError, match="visibly identify the AI"):
        build(bot_name="Phil Livesley")


def test_plan_rejects_local_webhook():
    with pytest.raises(ValueError, match="cannot be localhost"):
        build(realtime_webhook_url="https://localhost/recall")


def test_plan_rejects_non_https_meeting_url():
    with pytest.raises(ValueError, match="public HTTPS URL"):
        build(meeting_url="http://zoom.us/j/123")
