"""Completed VERIFY with verdict FAIL must be recoverable exactly once.

These cases use a real temporary git repository, not a fake workspace marker.
"""
from __future__ import annotations

import subprocess

from empire_os.coder.jobs import JobKind, LocalJobQueue
from empire_os.completion_verify_recovery import (
    recover_failed_completion_verifications,
)


def _completed_verify(tmp_path, verdict="FAIL"):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    source = tmp_path / "empire_os/m.py"
    source.parent.mkdir(parents=True)
    source.write_text("VALUE = 1\n", encoding="utf-8")
    test = tmp_path / "tests/test_m.py"
    test.parent.mkdir(parents=True)
    test.write_text("def test_m():\n    assert True\n")
    queue = LocalJobQueue(tmp_path)
    pending = queue.enqueue(
        task_id="verify-demo",
        kind=JobKind.VERIFY,
        payload={
            "completion_item_ids": ["check_a", "check_b", "check_c"],
            "completion_checklist_lines": [15, 19, 23],
            "changed_files": ["empire_os/m.py"],
            "tests": ["tests/test_m.py"],
            "execution_authority": "none",
        },
        priority=90,
    )
    claimed = queue.claim_specific(pending.id)
    assert claimed is not None
    terminal = queue.complete(claimed, {
        "verification": {"verdict": verdict},
        "production_mutation": False,
    })
    return queue, terminal


def _recon(job_id, *, state="NEEDS_WIRING_OR_TEST_FIX"):
    return {
        "status": "AVAILABLE",
        "items": [
            {"item_id": value, "state": state, "verification_job_id": job_id}
            for value in ("check_a", "check_b", "check_c")
        ],
    }


def test_completed_failed_verdict_retries_once_for_three_items(tmp_path):
    queue, original = _completed_verify(tmp_path)
    first = recover_failed_completion_verifications(
        tmp_path, reconciliation=_recon(original.id),
    )
    assert first["queued_group_count"] == 1
    assert first["queued_item_count"] == 3
    pending = queue.list_pending(kind=JobKind.VERIFY)
    assert len(pending) == 1
    assert pending[0].payload["recovery_of_verify_job_id"] == original.id
    assert pending[0].payload["completion_item_ids"] == [
        "check_a", "check_b", "check_c"
    ]
    assert pending[0].payload["completion_checklist_lines"] == [15, 19, 23]
    assert pending[0].payload["execution_authority"] == "none"
    again = recover_failed_completion_verifications(
        tmp_path, reconciliation=_recon(original.id),
    )
    assert again["queued_group_count"] == 0
    assert len(queue.list_pending(kind=JobKind.VERIFY)) == 1


def test_completed_pass_does_not_get_a_retry(tmp_path):
    queue, original = _completed_verify(tmp_path, verdict="PASS")
    result = recover_failed_completion_verifications(
        tmp_path, reconciliation=_recon(original.id),
    )
    assert result["queued_group_count"] == 0
    assert len(queue.list_pending(kind=JobKind.VERIFY)) == 0


def test_stale_old_completed_failure_is_not_retried_without_latest_reference(tmp_path):
    queue, original = _completed_verify(tmp_path)
    result = recover_failed_completion_verifications(
        tmp_path, reconciliation=_recon("coder_job_other"),
    )
    assert result["queued_group_count"] == 0


def test_no_longer_failed_items_do_not_retry_completed_failure(tmp_path):
    queue, original = _completed_verify(tmp_path)
    result = recover_failed_completion_verifications(
        tmp_path, reconciliation=_recon(original.id, state="NEEDS_LIVE_PROOF"),
    )
    assert result["queued_group_count"] == 0
    assert result["unresolved_item_count"] == 0


def test_changed_content_creates_at_most_one_new_revision_retry(tmp_path):
    queue, original = _completed_verify(tmp_path)
    first = recover_failed_completion_verifications(
        tmp_path, reconciliation=_recon(original.id),
    )
    assert first["queued_group_count"] == 1
    (tmp_path / "empire_os/m.py").write_text("VALUE = 2\n")
    second = recover_failed_completion_verifications(
        tmp_path, reconciliation=_recon(original.id),
    )
    assert second["queued_group_count"] == 1
    assert len(queue.list_pending(kind=JobKind.VERIFY)) == 2
