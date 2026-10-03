import json

from empire_os.live_queue_truth import build_live_queue_truth


def test_live_queue_truth_separates_checklist_from_active_queue(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/MASTER_REMAINING_CHECKLIST.md").write_text(
        "- [x] done\n- [ ] pending\n- [ ] pending2\n"
    )
    for bucket in (
        "pending", "running", "delegated", "completed", "failed"
    ):
        (tmp_path / f"runtime/coder/jobs/{bucket}").mkdir(
            parents=True,
            exist_ok=True,
        )
    (tmp_path / "runtime/coder/tasks").mkdir(parents=True)
    for bucket in (
        "ready", "running", "review", "done", "blocked", "failed"
    ):
        (tmp_path / f"runtime/departments/work/{bucket}").mkdir(
            parents=True,
            exist_ok=True,
        )

    result = build_live_queue_truth(tmp_path)

    assert result["canonical_checklist"]["pending"] == 2
    assert result["canonical_checklist"]["meaning"] == (
        "business_completion_scope_not_runnable_queue"
    )
    assert result["department_work_queue"]["active_count"] == 0
    assert result["coder_queue"]["active_pending_count"] == 0
    assert result["active_execution_backlog"] == 0


def test_historical_failed_jobs_are_not_active_backlog(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/MASTER_REMAINING_CHECKLIST.md").write_text("")
    for bucket in (
        "pending", "running", "delegated", "completed", "failed"
    ):
        (tmp_path / f"runtime/coder/jobs/{bucket}").mkdir(
            parents=True,
            exist_ok=True,
        )
    (tmp_path / "runtime/coder/tasks").mkdir(parents=True)
    for bucket in (
        "ready", "running", "review", "done", "blocked", "failed"
    ):
        (tmp_path / f"runtime/departments/work/{bucket}").mkdir(
            parents=True,
            exist_ok=True,
        )
    (tmp_path / "runtime/coder/jobs/failed/x.json").write_text(
        json.dumps({"kind": "PLAN"})
    )

    result = build_live_queue_truth(tmp_path)

    assert result["coder_queue"]["historical_failed_count"] == 1
    assert result["coder_queue"][
        "historical_failed_is_active_backlog"
    ] is False
    assert result["active_execution_backlog"] == 0
