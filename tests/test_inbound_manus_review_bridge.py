"""OpenManus owner handoff is durable, idempotent, and never dispatches."""
from datetime import datetime, timezone
from pathlib import Path
import json
import subprocess
import sys
import pytest

from empire_os.inbound_manus_review_bridge import OfflineManusReviewOutbox

COMMIT = "a" * 40
NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)


def test_stage_same_review_is_once_without_worker_or_customer_data(tmp_path):
    db = tmp_path / "review.db"
    with OfflineManusReviewOutbox(db) as outbox:
        first, created = outbox.stage(code_commit=COMMIT, at=NOW)
        assert created
        second, created = outbox.stage(code_commit=COMMIT, at=NOW)
        assert not created
        assert first == second
        assert first.execution_authority == "none"
        assert not first.browser_actions
        assert not first.customer_data_allowed
        assert outbox.summary()["queued_for_existing_owner"] == 1
        assert outbox.summary()["jobs_dispatched"] == 0
        assert outbox.summary()["worker_connected"] is False
    with OfflineManusReviewOutbox(db, read_only=True) as outbox:
        assert len(outbox.listing()) == 1
        with pytest.raises(ValueError, match="readonly"):
            outbox.stage(code_commit=COMMIT, at=NOW)


@pytest.mark.parametrize("wrong", ["", "abc", "not-sha-" + "a" * 32, "a" * 39 + "Z"])
def test_bad_commit_or_unapproved_source_refused(tmp_path, wrong):
    with OfflineManusReviewOutbox(tmp_path / "jobs.db") as outbox:
        with pytest.raises(ValueError, match="full_git"):
            outbox.stage(code_commit=wrong, at=NOW)
        with pytest.raises(ValueError, match="allowlisted"):
            outbox.stage(code_commit=COMMIT, source_doc="../private.env", at=NOW)


def test_cli_does_not_trigger_worker_and_never_creates_on_readonly(tmp_path):
    db = tmp_path / "manus.db"
    script = ["-B", "-m", "scripts.review_inbound_openmanus_handoff_20261020"]
    def run(*args):
        return subprocess.run([sys.executable, *script, *args], capture_output=True, text=True)
    absent = run("--outbox", str(db), "--read-only")
    assert absent.returncode != 0 and not db.exists()
    staged = run("--outbox", str(db), "--code-commit", COMMIT, "--stage-offline-only")
    assert staged.returncode == 0, staged.stderr
    result = json.loads(staged.stdout)
    assert result["queued_for_existing_owner"] == 1
    assert result["jobs_dispatched"] == 0
    assert result["created"] is True
    second = run("--outbox", str(db), "--code-commit", COMMIT, "--stage-offline-only")
    assert json.loads(second.stdout)["created"] is False
    read = run("--outbox", str(db), "--read-only")
    assert json.loads(read.stdout)["queued_for_existing_owner"] == 1
