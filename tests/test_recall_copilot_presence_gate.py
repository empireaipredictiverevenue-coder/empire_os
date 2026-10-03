from datetime import datetime, timedelta, timezone

import pytest

from empire_os.digital_avatar import (
    AvatarMeetingMode,
    AvatarMeetingSession,
    DigitalAvatarIdentity,
)
from empire_os.digital_avatar_presence_token import issue_avatar_presence_token
from empire_os.recall_copilot_output_media import (
    build_recall_copilot_output_media_plan,
)
from empire_os.recall_copilot_presence_gate import (
    RecallCopilotPresenceApproval,
    authorize_recall_copilot_presence_start,
    output_media_plan_sha256,
    start_recall_copilot_presence,
    stop_recall_copilot_presence,
)


NOW = datetime(2026, 10, 2, 19, 30, tzinfo=timezone.utc)
SECRET = "presence-secret-" + ("x" * 32)


def identity():
    return DigitalAvatarIdentity(
        avatar_id="avatar-phil-v1",
        owner_name="Phil Livesley",
        display_name="Phil — Empire AI Digital Avatar",
        organisation_name="Empire AI",
        disclosure_text="I am Phil's authorised Empire AI Digital Avatar.",
        owner_consent_evidence_ref="consent:phil:avatar:v1",
        voice_profile_ref="voice:phil:v1",
        visual_profile_ref="visual:phil:v1",
    )


def plan(ttl_seconds=300):
    token = issue_avatar_presence_token(
        secret=SECRET,
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        bot_id="bot-123",
        now=NOW,
        ttl_seconds=ttl_seconds,
        nonce="presence-gate-test",
    )
    session = AvatarMeetingSession(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        provider="recall",
        mode=AvatarMeetingMode.COPILOT,
        disclosure_announced=True,
    )
    return build_recall_copilot_output_media_plan(
        identity=identity(),
        session=session,
        bot_id="bot-123",
        region="eu-central-1",
        presence_base_url="https://empire-ai.co.uk/avatar/presence",
        presence_token=token,
    )


def approval(value=None, **overrides):
    value = value or plan()
    values = {
        "meeting_id": "meeting-001",
        "avatar_id": "avatar-phil-v1",
        "bot_id": "bot-123",
        "approved_by": "Phil Livesley",
        "approval_evidence_ref": "approval:presence:meeting-001:v1",
        "approved_at": "2026-10-02T19:29:00+00:00",
        "expires_at": "2026-10-02T19:34:00+00:00",
        "plan_sha256": output_media_plan_sha256(value),
    }
    values.update(overrides)
    return RecallCopilotPresenceApproval(**values)


class FakeTransport:
    def __init__(self, *, post_status=200, delete_status=204):
        self.post_status = post_status
        self.delete_status = delete_status
        self.posts = []
        self.deletes = []

    def post_json(self, **kwargs):
        self.posts.append(kwargs)
        return self.post_status, {}, {}

    def delete_json(self, **kwargs):
        self.deletes.append(kwargs)
        return self.delete_status, {}, {}


def test_presence_start_authorization_grants_presence_only():
    value = plan()
    authorized = authorize_recall_copilot_presence_start(
        identity=identity(),
        plan=value,
        approval=approval(value),
        now=NOW,
    )
    assert authorized.output_media_start_allowed is True
    assert authorized.speech_execution_allowed is False
    assert authorized.commercial_execution_allowed is False
    assert authorized.execution_authority == "copilot_presence_start_only"


def test_presence_start_calls_recall_with_exact_plan_but_no_speech_authority():
    value = plan()
    authorized = authorize_recall_copilot_presence_start(
        identity=identity(),
        plan=value,
        approval=approval(value),
        now=NOW,
    )
    transport = FakeTransport()
    result = start_recall_copilot_presence(
        authorization=authorized,
        identity=identity(),
        api_key="test-key",
        transport=transport,
        now=NOW,
    )
    assert result["presence_active"] is True
    assert result["speech_execution_allowed"] is False
    assert result["commercial_execution_allowed"] is False
    assert len(transport.posts) == 1
    call = transport.posts[0]
    assert call["url"] == value.endpoint
    assert call["payload"] == value.request_body
    assert call["headers"]["Authorization"] == "Token test-key"


def test_presence_approval_is_rechecked_at_provider_call():
    value = plan(ttl_seconds=600)
    approved = approval(
        value,
        expires_at="2026-10-02T19:31:00+00:00",
    )
    authorized = authorize_recall_copilot_presence_start(
        identity=identity(),
        plan=value,
        approval=approved,
        now=NOW,
    )
    transport = FakeTransport()
    with pytest.raises(ValueError, match="approval not active"):
        start_recall_copilot_presence(
            authorization=authorized,
            identity=identity(),
            api_key="test-key",
            transport=transport,
            now=NOW + timedelta(minutes=2),
        )
    assert transport.posts == []


def test_presence_token_expiry_blocks_start_even_if_approval_is_active():
    value = plan(ttl_seconds=30)
    with pytest.raises(ValueError, match="session token expired"):
        authorize_recall_copilot_presence_start(
            identity=identity(),
            plan=value,
            approval=approval(
                value,
                expires_at="2026-10-02T19:40:00+00:00",
            ),
            now=NOW + timedelta(seconds=31),
        )


def test_plan_drift_invalidates_presence_approval():
    first = plan()
    first_approval = approval(first)
    second_token = issue_avatar_presence_token(
        secret=SECRET,
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        bot_id="bot-123",
        now=NOW,
        nonce="different-token",
    )
    session = AvatarMeetingSession(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        provider="recall",
        mode=AvatarMeetingMode.COPILOT,
        disclosure_announced=True,
    )
    changed = build_recall_copilot_output_media_plan(
        identity=identity(),
        session=session,
        bot_id="bot-123",
        region="eu-central-1",
        presence_base_url="https://empire-ai.co.uk/avatar/presence",
        presence_token=second_token,
    )
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        authorize_recall_copilot_presence_start(
            identity=identity(),
            plan=changed,
            approval=first_approval,
            now=NOW,
        )


def test_presence_stop_is_available_as_fail_safe_without_reapproval():
    value = plan()
    authorized = authorize_recall_copilot_presence_start(
        identity=identity(),
        plan=value,
        approval=approval(value),
        now=NOW,
    )
    transport = FakeTransport()
    result = stop_recall_copilot_presence(
        authorization=authorized,
        api_key="test-key",
        transport=transport,
    )
    assert result["presence_active"] is False
    assert result["output_media_stop_performed"] is True
    assert result["execution_authority"] == "presence_stop_only"
    assert transport.deletes[0]["payload"] == {"camera": True}


def test_recall_start_failure_is_not_reported_as_active():
    value = plan()
    authorized = authorize_recall_copilot_presence_start(
        identity=identity(),
        plan=value,
        approval=approval(value),
        now=NOW,
    )
    with pytest.raises(RuntimeError, match="start failed with status 409"):
        start_recall_copilot_presence(
            authorization=authorized,
            identity=identity(),
            api_key="test-key",
            transport=FakeTransport(post_status=409),
            now=NOW,
        )
