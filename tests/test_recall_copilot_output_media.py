from datetime import datetime, timezone

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


NOW = datetime(2026, 10, 2, 19, 30, tzinfo=timezone.utc)
SECRET = "presence-secret-" + ("x" * 32)


def identity(**overrides):
    values = {
        "avatar_id": "avatar-phil-v1",
        "owner_name": "Phil Livesley",
        "display_name": "Phil — Empire AI Digital Avatar",
        "organisation_name": "Empire AI",
        "disclosure_text": "I am Phil's authorised Empire AI Digital Avatar.",
        "owner_consent_evidence_ref": "consent:phil:avatar:v1",
        "voice_profile_ref": "voice:phil:v1",
        "visual_profile_ref": "visual:phil:v1",
    }
    values.update(overrides)
    return DigitalAvatarIdentity(**values)


def session(mode=AvatarMeetingMode.COPILOT, disclosed=True):
    return AvatarMeetingSession(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        provider="recall",
        mode=mode,
        disclosure_announced=disclosed,
    )


def token(**overrides):
    values = {
        "secret": SECRET,
        "meeting_id": "meeting-001",
        "avatar_id": "avatar-phil-v1",
        "bot_id": "bot-123",
        "now": NOW,
        "nonce": "presence-output-test",
    }
    values.update(overrides)
    return issue_avatar_presence_token(**values)


def test_copilot_output_media_plan_is_bound_but_nonexecuting():
    plan = build_recall_copilot_output_media_plan(
        identity=identity(),
        session=session(),
        bot_id="bot-123",
        region="eu-central-1",
        presence_base_url="https://empire-ai.co.uk/avatar/presence",
        presence_token=token(),
    )
    assert plan.endpoint == (
        "https://eu-central-1.recall.ai/api/v1/bot/"
        "bot-123/output_media/"
    )
    assert plan.request_body["camera"]["kind"] == "webpage"
    assert plan.request_body["camera"]["config"]["url"].startswith(
        "https://empire-ai.co.uk/avatar/presence?token="
    )
    assert plan.voice_profile_ref == "voice:phil:v1"
    assert plan.visual_profile_ref == "visual:phil:v1"
    assert plan.output_media_start_allowed is False
    assert plan.output_media_start_performed is False
    assert plan.speech_execution_allowed is False
    assert plan.commercial_execution_allowed is False
    assert plan.execution_authority == "none"


def test_output_media_requires_disclosed_copilot_mode():
    with pytest.raises(ValueError, match="COPILOT mode"):
        build_recall_copilot_output_media_plan(
            identity=identity(),
            session=session(AvatarMeetingMode.SHADOW),
            bot_id="bot-123",
            region="eu-central-1",
            presence_base_url="https://empire-ai.co.uk/avatar/presence",
            presence_token=token(),
        )
    with pytest.raises(ValueError, match="AI disclosure"):
        build_recall_copilot_output_media_plan(
            identity=identity(),
            session=session(disclosed=False),
            bot_id="bot-123",
            region="eu-central-1",
            presence_base_url="https://empire-ai.co.uk/avatar/presence",
            presence_token=token(),
        )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"voice_profile_ref": None}, "voice profile"),
        ({"visual_profile_ref": None}, "visual profile"),
    ],
)
def test_output_media_requires_bound_clone_identity(kwargs, message):
    with pytest.raises(ValueError, match=message):
        build_recall_copilot_output_media_plan(
            identity=identity(**kwargs),
            session=session(),
            bot_id="bot-123",
            region="eu-central-1",
            presence_base_url="https://empire-ai.co.uk/avatar/presence",
            presence_token=token(),
        )


def test_output_media_token_is_bound_to_exact_recall_bot():
    with pytest.raises(ValueError, match="token bot mismatch"):
        build_recall_copilot_output_media_plan(
            identity=identity(),
            session=session(),
            bot_id="bot-other",
            region="eu-central-1",
            presence_base_url="https://empire-ai.co.uk/avatar/presence",
            presence_token=token(),
        )


def test_presence_base_url_cannot_be_loopback_or_embed_existing_token():
    with pytest.raises(ValueError, match="loopback"):
        build_recall_copilot_output_media_plan(
            identity=identity(),
            session=session(),
            bot_id="bot-123",
            region="eu-central-1",
            presence_base_url="https://localhost/avatar/presence",
            presence_token=token(),
        )
    with pytest.raises(ValueError, match="must not contain token"):
        build_recall_copilot_output_media_plan(
            identity=identity(),
            session=session(),
            bot_id="bot-123",
            region="eu-central-1",
            presence_base_url=(
                "https://empire-ai.co.uk/avatar/presence?token=old"
            ),
            presence_token=token(),
        )
