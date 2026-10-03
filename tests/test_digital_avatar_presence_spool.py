import json

import pytest

from empire_os.digital_avatar_presence_spool import FilePresenceTranscriptSpool
from empire_os.digital_avatar_presence_transcript import (
    PresenceTranscriptObservation,
)


def observation(**overrides):
    values = {
        "observation_id": "presence-transcript:abc123",
        "meeting_id": "meeting-001",
        "avatar_id": "avatar-phil-v1",
        "bot_id": "bot-123",
        "participant_ref": "recall-participant:7",
        "participant_name": "Buyer",
        "text": "Can you deploy this quickly?",
        "received_at": "2026-10-02T20:00:00+00:00",
        "is_final": True,
    }
    values.update(overrides)
    return PresenceTranscriptObservation(**values)


def test_presence_observation_spools_privately_without_truth_upgrade(tmp_path):
    spool = FilePresenceTranscriptSpool(tmp_path / "presence")
    receipt = spool.enqueue(observation())
    assert receipt.duplicate is False
    assert receipt.truth_class == "SESSION_OBSERVED"
    assert receipt.canonical_truth_written is False
    assert receipt.commercial_truth_written is False
    assert receipt.execution_authority == "none"

    files = list((tmp_path / "presence").glob("*.json"))
    assert len(files) == 1
    assert oct(files[0].stat().st_mode & 0o777) == "0o600"
    record = json.loads(files[0].read_text())
    assert record["raw_audio_persisted"] is False
    assert record["canonical_truth_written"] is False
    assert record["commercial_truth_written"] is False


def test_presence_spool_is_idempotent(tmp_path):
    spool = FilePresenceTranscriptSpool(tmp_path / "presence")
    first = spool.enqueue(observation())
    second = spool.enqueue(observation())
    assert first.spool_id == second.spool_id
    assert second.duplicate is True
    assert len(list((tmp_path / "presence").glob("*.json"))) == 1


def test_presence_spool_rejects_truth_or_execution_escalation(tmp_path):
    spool = FilePresenceTranscriptSpool(tmp_path / "presence")
    with pytest.raises(ValueError, match="canonical evidence"):
        spool.enqueue(observation(canonical_evidence=True))
    with pytest.raises(ValueError, match="commercial truth"):
        spool.enqueue(observation(commercial_truth_allowed=True))
    with pytest.raises(ValueError, match="speech authority"):
        spool.enqueue(observation(speech_execution_allowed=True))
    with pytest.raises(ValueError, match="execution authority"):
        spool.enqueue(observation(execution_authority="live"))
