import json
from datetime import datetime, timezone
from pathlib import Path

from empire_os.completion_closure_reconciler import (
    reconcile_completion_closure,
)


NOW = datetime(2026, 10, 3, 0, 0, tzinfo=timezone.utc)


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")


def _repo(tmp_path):
    checklist = tmp_path / "docs/MASTER_REMAINING_CHECKLIST.md"
    _write(
        checklist,
        "# Demo\n"
        "## Revenue\n"
        "- [ ] Verified feature\n"
        "- [ ] Tests only feature\n",
    )
    return checklist


def test_verify_pass_alone_never_closes(tmp_path):
    checklist = _repo(tmp_path)
    _write(
        tmp_path / "runtime/coder/jobs/completed/verify.json",
        {
            "id": "verify-1",
            "kind": "VERIFY",
            "status": "COMPLETED",
            "payload": {
                "completion_checklist_lines": [4],
                "changed_files": ["empire_os/x.py"],
                "tests": ["tests/test_x.py"],
            },
            "result": {"verification": {"verdict": "PASS"}},
        },
    )

    result = reconcile_completion_closure(tmp_path, now=NOW)

    assert result["applied_closure_count"] == 0
    assert result["state_counts"]["NEEDS_LIVE_PROOF"] == 1
    assert "- [ ] Tests only feature" in checklist.read_text()


def test_exact_live_checkpoint_plus_verify_closes_only_matching_row(tmp_path):
    checklist = _repo(tmp_path)
    _write(
        tmp_path / "runtime/coder/jobs/completed/verify.json",
        {
            "id": "verify-1",
            "kind": "VERIFY",
            "status": "COMPLETED",
            "payload": {
                "completion_checklist_lines": [3],
                "changed_files": ["empire_os/x.py"],
                "tests": ["tests/test_x.py"],
            },
            "result": {"verification": {"verdict": "PASS"}},
        },
    )
    _write(
        tmp_path
        / "runtime/execution_plane/completion_checkpoints/live.json",
        {
            "stage": "LIVE_VERIFY_DONE",
            "state": "DONE",
            "checklist_lines": [3],
            "evidence_refs": ["runtime:x"],
        },
    )

    result = reconcile_completion_closure(tmp_path, now=NOW)

    assert result["applied_closure_count"] == 1
    text = checklist.read_text()
    assert "- [x] Verified feature" in text
    assert "- [ ] Tests only feature" in text


def test_failed_verify_cannot_be_overridden_without_pass(tmp_path):
    checklist = _repo(tmp_path)
    _write(
        tmp_path / "runtime/coder/jobs/failed/verify.json",
        {
            "id": "verify-1",
            "kind": "VERIFY",
            "status": "FAILED",
            "payload": {"completion_checklist_lines": [3]},
            "result": {},
        },
    )
    _write(
        tmp_path
        / "runtime/execution_plane/completion_checkpoints/live.json",
        {
            "stage": "LIVE_VERIFY_DONE",
            "state": "DONE",
            "checklist_lines": [3],
        },
    )

    result = reconcile_completion_closure(tmp_path, now=NOW)

    assert result["applied_closure_count"] == 0
    assert result["state_counts"]["VERIFY_FAILED"] == 1
    assert "- [ ] Verified feature" in checklist.read_text()


def test_apply_false_is_observe_only(tmp_path):
    checklist = _repo(tmp_path)
    _write(
        tmp_path / "runtime/coder/jobs/completed/verify.json",
        {
            "id": "verify-1",
            "kind": "VERIFY",
            "status": "COMPLETED",
            "payload": {"completion_checklist_lines": [3]},
            "result": {"verification": {"verdict": "PASS"}},
        },
    )
    _write(
        tmp_path
        / "runtime/execution_plane/completion_checkpoints/live.json",
        {
            "stage": "LIVE_VERIFY_DONE",
            "state": "DONE",
            "checklist_lines": [3],
        },
    )

    result = reconcile_completion_closure(
        tmp_path,
        apply=False,
        now=NOW,
    )

    assert result["eligible_exact_closure_count"] == 1
    assert result["applied_closure_count"] == 0
    assert "- [ ] Verified feature" in checklist.read_text()
