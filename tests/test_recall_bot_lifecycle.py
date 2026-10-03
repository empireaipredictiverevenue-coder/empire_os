import pytest

from empire_os.recall_bot_lifecycle import normalize_verified_recall_lifecycle


def payload(code="in_call_recording", event=None, **metadata_overrides):
    metadata = {
        "empire_meeting_id": "meeting-001",
        "empire_avatar_id": "avatar-phil-v1",
        "empire_platform": "zoom",
        "empire_mode": "shadow",
        "execution_authority": "none",
    }
    metadata.update(metadata_overrides)
    return {
        "event": event or f"bot.{code}",
        "data": {
            "data": {
                "code": code,
                "sub_code": None,
                "updated_at": "2026-10-02T18:00:00+00:00",
            },
            "bot": {
                "id": "bot-123",
                "metadata": metadata,
            },
        },
    }


def test_recording_status_is_verified_meeting_state():
    item = normalize_verified_recall_lifecycle(
        payload=payload(),
        verified=True,
    )
    assert item.status_code == "in_call_recording"
    assert item.joined_meeting is True
    assert item.recording_active is True
    assert item.terminal is False
    assert item.truth_class == "VERIFIED"
    assert item.binding.avatar_id == "avatar-phil-v1"
    assert item.execution_authority == "none"


def test_waiting_room_is_not_treated_as_joined():
    item = normalize_verified_recall_lifecycle(
        payload=payload("in_waiting_room"),
        verified=True,
    )
    assert item.joined_meeting is False
    assert item.recording_active is False


def test_fatal_is_terminal_and_preserves_subcode():
    value = payload("fatal")
    value["data"]["data"]["sub_code"] = "meeting_not_found"
    item = normalize_verified_recall_lifecycle(
        payload=value,
        verified=True,
    )
    assert item.fatal is True
    assert item.terminal is True
    assert item.sub_code == "meeting_not_found"


def test_unknown_future_bot_status_is_preserved_not_crashed():
    item = normalize_verified_recall_lifecycle(
        payload=payload("future_status_code"),
        verified=True,
    )
    assert item.status_code == "future_status_code"
    assert item.joined_meeting is False
    assert item.terminal is False


def test_unverified_status_fails_closed():
    with pytest.raises(ValueError, match="unverified Recall lifecycle"):
        normalize_verified_recall_lifecycle(
            payload=payload(),
            verified=False,
        )


def test_status_with_non_shadow_metadata_fails_closed():
    with pytest.raises(ValueError, match="not SHADOW mode"):
        normalize_verified_recall_lifecycle(
            payload=payload(empire_mode="close"),
            verified=True,
        )
