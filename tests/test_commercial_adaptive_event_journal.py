"""Offline durability tests for existing Ops Control's commercial event journal."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import os

import pytest

from empire_os.commercial_adaptive_event_journal import append_change_once
from empire_os.commercial_adaptive_ops_bridge import observe_ops_adaptive_commercial
from empire_os.conversation_control_operational_truth import inspect_conversation_evidence
from test_commercial_adaptive_intelligence_cli import _test_sources


NOW = datetime(2026, 10, 20, 10, tzinfo=timezone.utc)


def _proof(root):
    return inspect_conversation_evidence(root, now=NOW)


def _event(root):
    packet = observe_ops_adaptive_commercial(
        root=root, previous_ops_snapshot={},
        conversation_proof=_proof(root), now=NOW,
    )
    assert packet["change_event"] is not None
    return packet["change_event"]


def test_one_original_event_record_after_retries(tmp_path):
    _test_sources(tmp_path)
    event = _event(tmp_path)
    log = tmp_path / "events.jsonl"
    assert append_change_once(log, event) is True
    assert append_change_once(log, {**event, "observed_at": "2026-10-20T12:00:00Z"}) is False
    entries = [json.loads(line) for line in log.read_text().splitlines()]
    assert len(entries) == 1
    assert entries[0]["event_id"] == event["event_id"]
    assert entries[0]["outbound_sent"] is False
    assert "synthetic-thread-1" not in log.read_text()
    assert "private@" not in log.read_text()
    assert os.stat(log).st_mode & 0o077 == 0


def test_recovery_from_interrupted_append_is_bounded_and_idempotent(tmp_path):
    _test_sources(tmp_path)
    event = _event(tmp_path)
    log = tmp_path / "events.jsonl"
    append_change_once(log, event)
    with log.open("a") as fp:
        fp.write('{"incomplete":')
    assert append_change_once(log, event) is False
    lines = log.read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["event_id"] == event["event_id"]


def test_distinct_evidence_receipts_get_distinct_event_ids(tmp_path):
    _test_sources(tmp_path)
    first = _event(tmp_path)
    file = tmp_path / "runtime/conversation_recovery/latest.json"
    raw = json.loads(file.read_text())
    raw["owner_observation_annotation"] = "new-source-version"
    file.write_text(json.dumps(raw))
    second = _event(tmp_path)
    assert first["event_id"] != second["event_id"]
    log = tmp_path / "events.jsonl"
    assert append_change_once(log, first)
    assert append_change_once(log, second)
    assert len(log.read_text().splitlines()) == 2


@pytest.mark.parametrize("field,value", [
    ("execution_authority", "send"),
    ("outbound_sent", True),
    ("owner_dispatch_executed", True),
    ("event_id", "not-a-valid-id"),
    ("changed_owner_source_names", ["PRIVATE_CONTACT_NAME"]),
    ("changed_gate_names", ["SEND_NOW"]),
])
def test_untrusted_event_rejected_before_log_creation(tmp_path, field, value):
    _test_sources(tmp_path)
    event = _event(tmp_path)
    event[field] = value
    log = tmp_path / "events.jsonl"
    with pytest.raises(ValueError):
        append_change_once(log, event)
    assert not log.exists()


def test_ops_cycle_journal_runs_before_snapshot_replacement():
    script = Path("scripts/run_ops_control_cycle.py").read_text()
    first = script.index("append_change_once(")
    last = script.index("tmp.replace(OUTPUT)")
    assert first < last
    assert script.count("append_change_once(") == 1
