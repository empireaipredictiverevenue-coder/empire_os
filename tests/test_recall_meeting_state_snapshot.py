import json

import pytest

from empire_os.recall_meeting_state_snapshot import (
    build_recall_meeting_state_snapshot,
    materialize_recall_meeting_state_snapshot,
)


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def runtime_payload(status="in_waiting_room", *, fatal=False):
    return {
        "meeting_id": "meeting-001",
        "avatar_id": "avatar-phil-v1",
        "bot_id": "bot-123",
        "status_code": status,
        "sub_code": "meeting_not_found" if fatal else None,
        "updated_at": "2026-10-02T18:00:00+00:00",
        "event_count": 1,
        "waiting_room": status == "in_waiting_room",
        "joined_meeting": status in {"in_call_recording", "done"},
        "currently_in_call": status == "in_call_recording",
        "recording_active": status == "in_call_recording",
        "terminal": status in {"done", "fatal"},
        "fatal": fatal,
        "evidence_refs": ["recall-verification:msg:1:abc"],
        "truth_class": "VERIFIED",
        "polling_performed": False,
        "speech_execution": False,
        "commercial_execution": False,
        "execution_authority": "none",
    }


def guidance_payload():
    return {
        "meeting_id": "meeting-001",
        "avatar_id": "avatar-phil-v1",
        "observation_count": 3,
        "guidance": {
            "latest_buyer_utterance": {
                "text": "Can you show me proof?",
                "evidence_ref": "recall:evidence:1",
            },
            "recommended_action": {
                "action_key": "present_verified_case_evidence",
            },
            "human_takeover_required": False,
            "blockers": [],
        },
        "response_task": {
            "recommended_action_key": "present_verified_case_evidence",
            "requires_human_approval": True,
            "speech_execution_allowed": False,
        },
        "private_to_owner": True,
        "speech_execution": False,
        "execution_authority": "none",
    }


def test_lifecycle_only_snapshot_works_before_anyone_speaks(tmp_path):
    runtime = tmp_path / "runtime"
    write_json(runtime / "meeting-001.json", runtime_payload())
    state = build_recall_meeting_state_snapshot(
        meeting_id="meeting-001",
        guidance_root=tmp_path / "guidance",
        runtime_state_root=runtime,
    )
    assert state.avatar_id == "avatar-phil-v1"
    assert state.lifecycle_status == "in_waiting_room"
    assert state.waiting_room is True
    assert state.joined_meeting is False
    assert state.currently_in_call is False
    assert state.observation_count == 0
    assert "private_guidance_not_available" in state.blockers
    assert state.execution_authority == "none"


def test_snapshot_merges_runtime_and_private_guidance(tmp_path):
    runtime = tmp_path / "runtime"
    guidance = tmp_path / "guidance"
    write_json(runtime / "meeting-001.json", runtime_payload("in_call_recording"))
    write_json(guidance / "meeting-001.json", guidance_payload())
    state = build_recall_meeting_state_snapshot(
        meeting_id="meeting-001",
        guidance_root=guidance,
        runtime_state_root=runtime,
    )
    assert state.joined_meeting is True
    assert state.currently_in_call is True
    assert state.recording_active is True
    assert state.observation_count == 3
    assert state.latest_buyer_utterance["text"] == "Can you show me proof?"
    assert state.recommended_action["action_key"] == "present_verified_case_evidence"
    assert state.response_task["requires_human_approval"] is True
    assert state.blockers == ()
    assert state.speech_execution is False


def test_fatal_runtime_requires_human_takeover(tmp_path):
    runtime = tmp_path / "runtime"
    write_json(runtime / "meeting-001.json", runtime_payload("fatal", fatal=True))
    state = build_recall_meeting_state_snapshot(
        meeting_id="meeting-001",
        guidance_root=tmp_path / "guidance",
        runtime_state_root=runtime,
    )
    assert state.fatal is True
    assert state.terminal is True
    assert state.human_takeover_required is True
    assert "recall_bot_fatal" in state.blockers


def test_snapshot_rejects_path_like_meeting_id(tmp_path):
    with pytest.raises(ValueError, match="invalid meeting_id"):
        build_recall_meeting_state_snapshot(
            meeting_id="../../etc/passwd",
            guidance_root=tmp_path / "guidance",
            runtime_state_root=tmp_path / "runtime",
        )


def test_snapshot_materialization_is_private(tmp_path):
    runtime = tmp_path / "runtime"
    guidance = tmp_path / "guidance"
    out = tmp_path / "state"
    write_json(runtime / "meeting-001.json", runtime_payload("in_call_recording"))
    write_json(guidance / "meeting-001.json", guidance_payload())
    target = materialize_recall_meeting_state_snapshot(
        meeting_id="meeting-001",
        guidance_root=guidance,
        runtime_state_root=runtime,
        output_root=out,
    )
    assert target.name == "meeting-001.json"
    assert oct(target.stat().st_mode & 0o777) == "0o600"
