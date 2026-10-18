"""The existing buyer acquisition cadence may refresh only six Workspace reply anchors."""
from __future__ import annotations
import json
import subprocess
from types import SimpleNamespace

from scripts import refresh_buyer_acquisition_team as team


def success(**updates):
    payload = {
        "status": "WORKSPACE_SENT_ANCHORS_VERIFIED_REVIEW_ONLY",
        "source_scan_complete": True,
        "snapshot_written": True,
        "verified_sent_anchors_in_live_mailbox": 6,
        "new_inbound_header_candidates": 0,
        "outbound_sent": False,
        "database_writes": False,
    }
    payload.update(updates)
    return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="private ignored")


def test_existing_timer_uses_bounded_non_sending_reader(monkeypatch):
    calls = []
    monkeypatch.setattr(team.subprocess, "run", lambda *a, **k: (calls.append((a, k)) or success()))
    result = team.refresh_existing_workspace_reply_snapshot()
    assert result == {
        "status": "SIX_THREAD_WORKSPACE_SNAPSHOT_REFRESHED",
        "verified_sent_anchors": 6,
        "new_inbound_header_candidates": 0,
        "outbound_sent": False,
        "database_writes": False,
    }
    args, opts = calls[0]
    assert args[0][1:] == ("-B", "-m", "scripts.poll_workspace_solar_outreach_readonly", "--write")
    assert opts["capture_output"] is True
    assert opts["timeout"] <= 35
    assert opts["check"] is False


def test_existing_timer_reports_fresh_candidates_only(monkeypatch):
    monkeypatch.setattr(team.subprocess, "run",
                        lambda *a, **k: success(new_inbound_header_candidates=2))
    result = team.refresh_existing_workspace_reply_snapshot()
    assert result["new_inbound_header_candidates"] == 2
    assert "email" not in str(result).lower()


def test_existing_timer_does_not_promote_incomplete_scan(monkeypatch):
    monkeypatch.setattr(team.subprocess, "run",
                        lambda *a, **k: success(verified_sent_anchors_in_live_mailbox=5))
    result = team.refresh_existing_workspace_reply_snapshot()
    assert result["status"] == "HELD_WORKSPACE_SNAPSHOT_NOT_REFRESHED"


def test_existing_timer_refuses_claim_of_sent_mail_or_db_write(monkeypatch):
    for payload in (success(outbound_sent=True), success(database_writes=True)):
        monkeypatch.setattr(team.subprocess, "run", lambda *a, **k: payload)
        result = team.refresh_existing_workspace_reply_snapshot()
        assert result["status"] == "HELD_WORKSPACE_SNAPSHOT_NOT_REFRESHED"


def test_existing_timer_fails_closed_on_timeout_without_provider_error(monkeypatch):
    def timeout(*a, **k):
        raise subprocess.TimeoutExpired(cmd="confidential", timeout=35)
    monkeypatch.setattr(team.subprocess, "run", timeout)
    result = team.refresh_existing_workspace_reply_snapshot()
    assert result["status"] == "HELD_WORKSPACE_SNAPSHOT_NOT_REFRESHED"
    assert "confidential" not in str(result)
