import json

from empire_os.recall_meeting_runtime_state import (
    build_recall_meeting_runtime_state,
    refresh_recall_meeting_runtime_state,
)


def record(status, updated_at, *, queue_id):
    return {
        "queue_id": queue_id,
        "truth_class": "VERIFIED",
        "execution_authority": "none",
        "source_verification": {
            "verified": True,
            "webhook_id": queue_id,
            "webhook_timestamp": "1790964000",
            "payload_sha256": "a" * 64,
        },
        "lifecycle": {
            "event": f"bot.{status}",
            "bot_id": "bot-123",
            "status_code": status,
            "sub_code": None,
            "updated_at": updated_at,
            "binding": {
                "bot_id": "bot-123",
                "meeting_id": "meeting-001",
                "avatar_id": "avatar-phil-v1",
                "platform": "zoom",
                "mode": "shadow",
                "execution_authority": "none",
                "truth_class": "VERIFIED",
            },
            "joined_meeting": status in {
                "in_call_not_recording",
                "in_call_recording",
                "call_ended",
                "done",
            },
            "recording_active": status == "in_call_recording",
            "terminal": status in {"done", "fatal"},
            "fatal": status == "fatal",
            "truth_class": "VERIFIED",
            "execution_authority": "none",
        },
    }


def test_latest_verified_lifecycle_becomes_runtime_state():
    state = build_recall_meeting_runtime_state(
        [
            record(
                "joining_call",
                "2026-10-02T18:00:00+00:00",
                queue_id="evt-1",
            ),
            record(
                "in_waiting_room",
                "2026-10-02T18:00:05+00:00",
                queue_id="evt-2",
            ),
            record(
                "in_call_recording",
                "2026-10-02T18:00:10+00:00",
                queue_id="evt-3",
            ),
        ],
        meeting_id="meeting-001",
    )
    assert state is not None
    assert state.status_code == "in_call_recording"
    assert state.event_count == 3
    assert state.waiting_room is False
    assert state.joined_meeting is True
    assert state.currently_in_call is True
    assert state.recording_active is True
    assert state.polling_performed is False
    assert state.execution_authority == "none"
    assert len(state.evidence_refs) == 3


def test_no_matching_meeting_returns_none():
    state = build_recall_meeting_runtime_state(
        [record("joining_call", "2026-10-02T18:00:00+00:00", queue_id="evt-1")],
        meeting_id="meeting-other",
    )
    assert state is None


def test_refresh_materializes_private_runtime_state(tmp_path):
    lifecycle_root = tmp_path / "lifecycle"
    lifecycle_root.mkdir()
    first = record(
        "in_waiting_room",
        "2026-10-02T18:00:05+00:00",
        queue_id="evt-1",
    )
    second = record(
        "fatal",
        "2026-10-02T18:00:15+00:00",
        queue_id="evt-2",
    )
    second["lifecycle"]["sub_code"] = "meeting_not_found"
    (lifecycle_root / "1.json").write_text(json.dumps(first))
    (lifecycle_root / "2.json").write_text(json.dumps(second))

    target = tmp_path / "state" / "meeting-001.json"
    state = refresh_recall_meeting_runtime_state(
        lifecycle_root=lifecycle_root,
        meeting_id="meeting-001",
        output_path=target,
    )
    assert state is not None
    assert state.status_code == "fatal"
    assert state.fatal is True
    assert state.terminal is True
    assert state.sub_code == "meeting_not_found"
    assert target.is_file()
    assert oct(target.stat().st_mode & 0o777) == "0o600"


def test_terminal_meeting_is_not_reported_as_currently_in_call():
    state = build_recall_meeting_runtime_state(
        [
            record(
                "done",
                "2026-10-02T18:10:00+00:00",
                queue_id="evt-done",
            )
        ],
        meeting_id="meeting-001",
    )
    assert state is not None
    assert state.joined_meeting is True
    assert state.currently_in_call is False
    assert state.terminal is True
