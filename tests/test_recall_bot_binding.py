import pytest

from empire_os.recall_bot_binding import extract_recall_bot_binding


def payload(**metadata_overrides):
    metadata = {
        "empire_meeting_id": "meeting-001",
        "empire_avatar_id": "avatar-phil-v1",
        "empire_platform": "zoom",
        "empire_mode": "shadow",
        "execution_authority": "none",
    }
    metadata.update(metadata_overrides)
    return {
        "event": "transcript.data",
        "data": {
            "bot": {"id": "bot-123", "metadata": metadata},
            "transcript": {"id": "transcript-456"},
            "data": {
                "participant": {"id": 7, "name": "Buyer"},
                "words": [{"text": "Hello"}],
            },
        },
    }


def test_signed_bot_metadata_binds_empire_session():
    binding = extract_recall_bot_binding(payload())
    assert binding.bot_id == "bot-123"
    assert binding.meeting_id == "meeting-001"
    assert binding.avatar_id == "avatar-phil-v1"
    assert binding.platform.value == "zoom"
    assert binding.mode == "shadow"
    assert binding.execution_authority == "none"
    assert binding.truth_class == "VERIFIED"


def test_missing_avatar_binding_fails_closed():
    with pytest.raises(ValueError, match="meeting/avatar binding missing"):
        extract_recall_bot_binding(payload(empire_avatar_id=""))


def test_non_shadow_binding_fails_closed():
    with pytest.raises(ValueError, match="not SHADOW mode"):
        extract_recall_bot_binding(payload(empire_mode="close"))


def test_execution_authority_in_metadata_fails_closed():
    with pytest.raises(ValueError, match="no execution authority"):
        extract_recall_bot_binding(
            payload(execution_authority="governed_external")
        )


def test_unsupported_platform_fails_closed():
    with pytest.raises(ValueError, match="unsupported Empire meeting platform"):
        extract_recall_bot_binding(payload(empire_platform="carrier_pigeon"))
