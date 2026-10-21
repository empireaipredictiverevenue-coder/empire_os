"""No-progress retry gate wired to EmpireOS's existing dispatch and worker."""
import json
from pathlib import Path

import pytest

from empire_os.department_adapter_registry import (
    _worker_capabilities,
    eligible_specialist_reopen_reasons, has_existing_department_adapter,
)
from empire_os.department_work_queue import DepartmentWorkQueue
from empire_os.astra_department_dispatch import dispatch_executive_plan
from empire_os.department_worker import SAFE_COMMANDS as WORKER_SAFE_COMMANDS


def _step(target="missing_specialist", key="test_step"):
    return {
        "step_id": key,
        "goal_key": "existing_revenue_goal",
        "department_keys": ["sales_revenue"],
        "target_component": target,
        "action": "prepare_evidence",
        "authority": "observe",
        "auto_dispatch_eligible": True,
        "founder_gate_required": False,
        "intelligence_request": {"task": "read_only"},
        "success_condition": "evidence_or_real_blocker",
    }


def _publish_plan(root, step):
    path = root / "runtime/astra/executive_latest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"plan_id": "existing_plan", "plan": [step]}))


def test_authoritative_worker_registry_shared():
    from empire_os import department_worker
    direct, commands = _worker_capabilities(Path(department_worker.__file__).resolve().parents[1])
    assert commands == WORKER_SAFE_COMMANDS
    assert {"empire_coder", "agent_tool_execution_plane", "predictive_intelligence"} <= direct


@pytest.mark.parametrize("target", [
    "missing_specialist", "", "empire_coder_typo", "../empire_coder",
])
def test_unimplemented_targets_cannot_reopen(tmp_path, target):
    assert not has_existing_department_adapter(tmp_path, target)
    assert eligible_specialist_reopen_reasons(tmp_path, target) == ()


def test_safe_command_requires_present_script(tmp_path):
    target = "commercial_product_catalog"
    assert not has_existing_department_adapter(tmp_path, target)
    script = tmp_path / WORKER_SAFE_COMMANDS[target][0]
    script.parent.mkdir(parents=True)
    script.write_text("# a synthetic placeholder, not executed\n")
    worker = tmp_path / "empire_os/department_worker.py"
    worker.parent.mkdir(parents=True, exist_ok=True)
    worker.write_text(
        'SAFE_COMMANDS = {"commercial_product_catalog": '
        '("scripts/refresh_commercial_product_catalog.py", "runtime:test")}\n'
    )
    assert has_existing_department_adapter(tmp_path, target)
    assert eligible_specialist_reopen_reasons(tmp_path, target) == (
        "specialist_adapter_required",
    )


def test_blocked_missing_adapter_not_reopened_by_existing_dispatcher(tmp_path, monkeypatch):
    import empire_os.astra_department_dispatch as dispatch
    monkeypatch.setattr(
        dispatch, "auto_retrieve_for_astra",
        lambda *_: {"status": "no_relevant_company_bound_task"},
    )
    _publish_plan(tmp_path, _step())
    first = dispatch_executive_plan(tmp_path)
    assert first["queued_count"] == 1
    queue = DepartmentWorkQueue(tmp_path)
    claimed = queue.claim_next()
    assert claimed is not None
    queue.block(claimed, "specialist_adapter_required")
    # Existing Astra work must remain blocked until a real adapter is installed.
    again = dispatch_executive_plan(tmp_path)
    assert again["queued_count"] == 0
    assert again["existing_count"] == 1
    assert queue.counts()["blocked"] == 1
    assert queue.counts()["ready"] == 0


def test_new_adapter_allows_existing_dispatcher_to_resume_same_work(tmp_path, monkeypatch):
    import empire_os.astra_department_dispatch as dispatch
    monkeypatch.setattr(
        dispatch, "auto_retrieve_for_astra",
        lambda *_: {"status": "no_relevant_company_bound_task"},
    )
    _publish_plan(tmp_path, _step(target="empire_coder"))
    worker = tmp_path / "empire_os/department_worker.py"
    worker.parent.mkdir(parents=True)
    worker.write_text(
        'def _run_one_department_work_impl(item):\n'
        '    if item.target_component == "empire_coder":\n'
        '        return None\n'
    )
    queue = DepartmentWorkQueue(tmp_path)
    first = dispatch_executive_plan(tmp_path)
    assert first["queued_count"] == 1
    claimed = queue.claim_next()
    queue.block(claimed, "specialist_adapter_required")
    second = dispatch_executive_plan(tmp_path)
    assert second["queued_count"] == 1
    assert second["items"][0]["work_id"] == first["items"][0]["work_id"]
    assert queue.counts()["ready"] == 1
    assert queue.counts()["blocked"] == 0
    third = dispatch_executive_plan(tmp_path)
    assert third["queued_count"] == 0  # idempotent, no queue duplication


def test_real_outcome_evidence_hold_is_not_reopened(tmp_path, monkeypatch):
    import empire_os.astra_department_dispatch as dispatch
    monkeypatch.setattr(
        dispatch, "auto_retrieve_for_astra",
        lambda *_: {"status": "no_relevant_company_bound_task"},
    )
    _publish_plan(tmp_path, _step(target="predictive_intelligence"))
    queue = DepartmentWorkQueue(tmp_path)
    dispatch_executive_plan(tmp_path)
    queue.block(queue.claim_next(), "insufficient_verified_outcome_cohort")
    later = dispatch_executive_plan(tmp_path)
    assert later["queued_count"] == 0
    assert queue.counts()["blocked"] == 1
    assert queue.counts()["ready"] == 0


@pytest.mark.parametrize("input_goals, expected", [
    ([], {}),
    ([{"key": "revenue", "priority": 100, "status": "active"}], {"revenue": 87}),
    ([{"key": "evidence", "priority": 90, "status": "active"}], {"evidence": 82}),
    ([{"key": "weak", "priority": 10, "status": "active"}], {"weak": 80}),
    ([{"key": "disabled", "priority": 100, "status": "paused"}], {}),
    ([{"key": "bad", "priority": True, "status": "active"}], {}),
    ([{"key": "bad", "priority": 150, "status": "active"}], {}),
    ([{"key": "d", "priority": 100, "status": "active"},
      {"key": "d", "priority": 99, "status": "active"}], {}),
])
def test_existing_goal_priorities_are_bounded_and_fail_closed(input_goals, expected):
    from empire_os.astra_department_dispatch import _goal_priority_map
    assert _goal_priority_map({"goals": input_goals}) == expected


def test_goal_alignment_changes_only_safe_queue_order_not_authority(tmp_path, monkeypatch):
    import empire_os.astra_department_dispatch as dispatch
    monkeypatch.setattr(
        dispatch, "auto_retrieve_for_astra",
        lambda *_: {"status": "no_relevant_company_bound_task"},
    )
    goal_rows = [
        {"key": "commercial", "priority": 100, "status": "active"},
        {"key": "research", "priority": 89, "status": "active"},
    ]
    steps = [
        dict(_step(target="empire_coder", key="research_step"), goal_key="research"),
        dict(_step(target="empire_coder", key="commercial_step"), goal_key="commercial"),
        dict(_step(target="empire_coder", key="founder_step"), goal_key="commercial",
             founder_gate_required=True, authority="founder_gate"),
    ]
    path = tmp_path / "runtime/astra/executive_latest.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "plan_id": "existing_goals",
        "plan": steps,
        "goals": goal_rows,
    }))
    result = dispatch_executive_plan(tmp_path)
    assert result["queued_count"] == 2
    assert result["authority_blocked_count"] == 1
    assert result["goal_priority_applied_to_new_work_count"] == 2
    assert {row["effective_priority"] for row in result["items"]} == {82, 87}
    queue = DepartmentWorkQueue(tmp_path)
    highest = queue.claim_next()
    assert highest.goal_key == "commercial"
    assert highest.priority == 87
    assert highest.authority == "observe"
    next_item = queue.claim_next()
    assert next_item.goal_key == "research"
    assert next_item.priority == 82
    assert queue.claim_next() is None


def test_goal_alignment_does_not_override_legacy_on_existing_job(tmp_path, monkeypatch):
    import empire_os.astra_department_dispatch as dispatch
    monkeypatch.setattr(
        dispatch, "auto_retrieve_for_astra",
        lambda *_: {"status": "no_relevant_company_bound_task"},
    )
    _publish_plan(tmp_path, _step(target="empire_coder"))
    result = dispatch_executive_plan(tmp_path)
    assert result["items"][0]["effective_priority"] == 80
    plan_path = tmp_path / "runtime/astra/executive_latest.json"
    original = json.loads(plan_path.read_text())
    original["goals"] = [{"key": "existing_revenue_goal", "priority": 100, "status": "active"}]
    plan_path.write_text(json.dumps(original))
    later = dispatch_executive_plan(tmp_path)
    assert later["queued_count"] == 0
    assert later["items"][0]["effective_priority"] == 80
    assert later["goal_priority_applied_to_new_work_count"] == 0


def test_worker_direct_targets_and_registry_cannot_silently_diverge():
    from empire_os import department_worker
    direct, commands = _worker_capabilities(Path(department_worker.__file__).resolve().parents[1])
    assert "source_intelligence_review" in direct
    assert "empire_coder" in direct
    assert commands == department_worker.SAFE_COMMANDS


def test_repeated_dispatch_has_no_unproductive_specialist_wakes(tmp_path, monkeypatch):
    import empire_os.astra_department_dispatch as dispatch
    monkeypatch.setattr(
        dispatch, "auto_retrieve_for_astra",
        lambda *_: {"status": "no_relevant_company_bound_task"},
    )
    _publish_plan(tmp_path, _step(target="capability_not_built_yet"))
    queue = DepartmentWorkQueue(tmp_path)
    dispatch_executive_plan(tmp_path)
    queue.block(queue.claim_next(), "specialist_adapter_required")
    for _ in range(10):
        result = dispatch_executive_plan(tmp_path)
        assert result["queued_count"] == 0
        assert result["specialist_retry_held_count"] == 1
    assert queue.counts()["blocked"] == 1
    assert queue.counts()["running"] == 0
    assert queue.counts()["ready"] == 0
    assert len(list(queue.blocked.glob("*.json"))) == 1


def test_new_external_owner_worker_branch_is_detected_without_running_code(tmp_path):
    worker = tmp_path / "empire_os/department_worker.py"
    worker.parent.mkdir(parents=True)
    worker.write_text(
        '# if item.target_component == "fake_comment":\n'
        'def _run_one_department_work_impl(item):\n'
        '    if item.target_component == "new_research_adapter":\n'
        '        raise RuntimeError("must never execute")\n'
    )
    assert has_existing_department_adapter(tmp_path, "new_research_adapter")
    assert not has_existing_department_adapter(tmp_path, "fake_comment")
    assert not has_existing_department_adapter(tmp_path, "unknown_adapter")
    assert eligible_specialist_reopen_reasons(
        tmp_path, "new_research_adapter"
    ) == ("specialist_adapter_required",)


def test_symlinked_worker_outside_own_repo_does_not_create_a_capability(tmp_path):
    worker = tmp_path / "empire_os/department_worker.py"
    worker.parent.mkdir(parents=True)
    outside = tmp_path.parent / (tmp_path.name + "_external_worker.py")
    outside.write_text('if item.target_component == "unsafe_external":\n    pass\n')
    worker.symlink_to(outside)
    assert not has_existing_department_adapter(tmp_path, "unsafe_external")


def test_invalid_worker_source_is_fail_closed(tmp_path):
    worker = tmp_path / "empire_os/department_worker.py"
    worker.parent.mkdir(parents=True)
    worker.write_text('if this is not valid python:\n')
    assert not has_existing_department_adapter(tmp_path, "empire_coder")
    assert eligible_specialist_reopen_reasons(tmp_path, "empire_coder") == ()


def test_source_strings_cannot_fake_declared_adapter(tmp_path):
    worker = tmp_path / "empire_os/department_worker.py"
    worker.parent.mkdir(parents=True)
    worker.write_text(
        '"""\nif item.target_component == "fake_from_docstring":\n"""\n'
        'SAFE_COMMANDS = __import__("os").system("echo forbidden")\n'
        'def not_the_worker_handler(item):\n'
        '    if item.target_component == "fake_in_unrelated_function":\n'
        '        return None\n'
    )
    for target in ("fake_from_docstring", "fake_in_unrelated_function", "unknown"):
        assert not has_existing_department_adapter(tmp_path, target)
