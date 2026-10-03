import json

from empire_os.coder.jobs import JobKind, LocalJobQueue
from empire_os.completion_verify_recovery import (
    recover_failed_completion_verifications,
)


def _failed_verify(tmp_path):
    module = tmp_path / "empire_os/x.py"
    module.parent.mkdir(parents=True, exist_ok=True)
    module.write_text("VALUE = 1\n", encoding="utf-8")
    test = tmp_path / "tests/test_x.py"
    test.parent.mkdir(parents=True, exist_ok=True)
    test.write_text(
        "def test_x():\n    assert True\n",
        encoding="utf-8",
    )

    queue = LocalJobQueue(tmp_path)
    job = queue.enqueue(
        task_id="task-x",
        kind=JobKind.VERIFY,
        priority=90,
        payload={
            "changed_files": ["empire_os/x.py"],
            "tests": ["tests/test_x.py"],
            "completion_item_ids": ["check_x"],
            "completion_checklist_lines": [12],
            "execution_authority": "none",
        },
    )
    claimed = queue.claim_specific(job.id)
    assert claimed is not None
    queue.fail(claimed, "deterministic_verification_failed")
    return queue


def _reconciliation():
    return {
        "status": "AVAILABLE",
        "items": [
            {
                "item_id": "check_x",
                "state": "NEEDS_WIRING_OR_TEST_FIX",
            }
        ],
    }


def test_recovery_queues_failed_verify_once_for_same_content(tmp_path):
    queue = _failed_verify(tmp_path)

    first = recover_failed_completion_verifications(
        tmp_path,
        reconciliation=_reconciliation(),
    )
    second = recover_failed_completion_verifications(
        tmp_path,
        reconciliation=_reconciliation(),
    )

    assert first["queued_group_count"] == 1
    assert first["queued_item_count"] == 1
    assert second["queued_group_count"] == 0
    pending = queue.list_pending(kind=JobKind.VERIFY)
    assert len(pending) == 1
    assert pending[0].payload["recovery_of_verify_job_id"]


def test_recovery_allows_new_retry_after_relevant_content_changes(tmp_path):
    queue = _failed_verify(tmp_path)
    first = recover_failed_completion_verifications(
        tmp_path,
        reconciliation=_reconciliation(),
    )
    assert first["queued_group_count"] == 1

    (tmp_path / "empire_os/x.py").write_text(
        "VALUE = 2\n",
        encoding="utf-8",
    )
    second = recover_failed_completion_verifications(
        tmp_path,
        reconciliation=_reconciliation(),
    )

    assert second["queued_group_count"] == 1
    assert len(queue.list_pending(kind=JobKind.VERIFY)) == 2


def test_recovery_does_nothing_when_item_no_longer_failed(tmp_path):
    _failed_verify(tmp_path)
    result = recover_failed_completion_verifications(
        tmp_path,
        reconciliation={
            "status": "AVAILABLE",
            "items": [{"item_id": "check_x", "state": "NEEDS_LIVE_PROOF"}],
        },
    )

    assert result["queued_group_count"] == 0
    assert result["unresolved_item_count"] == 0
