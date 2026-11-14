"""End-to-end coordinator regression: ownership, retry suppression and truth."""
import json
import subprocess
from pathlib import Path

import empire_os.department_worker as worker
from empire_os.astra_department_dispatch import dispatch_executive_plan
from empire_os.astra_department_evaluator import evaluate_executive_plan
from empire_os.department_work_queue import DepartmentWorkQueue


def step(**changes):
    value = {
        "step_id": "exec_step_roofing_one",
        "goal_key": "restore_operating_truth",
        "department_keys": ["engineering", "operations_fulfilment"],
        "target_component": "ops_sentinel",
        "action": "refresh_predictive_cloud_truth",
        "authority": "observe",
        "auto_dispatch_eligible": True,
        "founder_gate_required": False,
        "intelligence_request": {"objective": "check actual components"},
        "evidence_refs": ["predictive_cloud:founder_directives"],
        "success_condition": "critical services live and current",
    }
    value.update(changes)
    return value


def publish(root, plan_id, steps):
    p = root / "runtime/astra/executive_latest.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"plan_id": plan_id, "plan": steps}))


def test_new_plan_reuses_blocked_work_and_evaluator_retains_ownership(tmp_path, monkeypatch):
    import empire_os.astra_department_dispatch as dispatch
    monkeypatch.setattr(dispatch, "auto_retrieve_for_astra",
                        lambda *_: {"status": "no_relevant_company_bound_task"})
    publish(tmp_path, "plan_one", [step()])
    first = dispatch_executive_plan(tmp_path)
    assert first["queued_count"] == 1
    queue = DepartmentWorkQueue(tmp_path)
    queue.block(queue.claim_next(), "predictive_cloud_components_unhealthy")
    publish(tmp_path, "plan_two", [step()])
    second = dispatch_executive_plan(tmp_path)
    assert second["queued_count"] == 0
    assert second["carried_forward_unresolved_count"] == 1
    assert second["items"][0]["work_id"] == first["items"][0]["work_id"]
    assert second["items"][0]["work_state"] == "BLOCKED"
    assert queue.counts()["blocked"] == 1
    state = evaluate_executive_plan(tmp_path)
    assert state["evaluation_state"] == "BLOCKED"
    assert state["undispatched_step_ids"] == []


def test_new_evidence_not_coalesced_into_old_work(tmp_path, monkeypatch):
    import empire_os.astra_department_dispatch as dispatch
    monkeypatch.setattr(dispatch, "auto_retrieve_for_astra",
                        lambda *_: {"status": "no_relevant_company_bound_task"})
    publish(tmp_path, "plan_one", [step()])
    first = dispatch_executive_plan(tmp_path)
    queue = DepartmentWorkQueue(tmp_path)
    queue.block(queue.claim_next(), "predictive_cloud_components_unhealthy")
    publish(tmp_path, "plan_two", [step(evidence_refs=["new:source:observation"])])
    second = dispatch_executive_plan(tmp_path)
    assert second["queued_count"] == 1
    assert second["carried_forward_unresolved_count"] == 0
    assert second["items"][0]["work_id"] != first["items"][0]["work_id"]


def test_ops_sentinel_does_not_report_unhealthy_as_complete(tmp_path, monkeypatch):
    publish(tmp_path, "plan_bad", [step()])
    dispatch_executive_plan(tmp_path)
    monkeypatch.setattr(worker.subprocess, "run",
                        lambda command, **kwargs: subprocess.CompletedProcess(
                            command, 0, stdout=json.dumps({
                                "component_count": 3, "available_component_count": 2,
                                "unavailable_components": ["revenue_pulse"],
                                "stale_components": [], "unknown_freshness_components": []
                            }), stderr=""))
    outcome = worker.run_one_department_work(tmp_path)
    assert outcome["state"] == "BLOCKED"
    assert outcome["blocker"] == "predictive_cloud_components_unhealthy"
    assert DepartmentWorkQueue(tmp_path).counts()["done"] == 0


def test_ops_sentinel_can_complete_when_all_evidence_is_current(tmp_path, monkeypatch):
    publish(tmp_path, "plan_good", [step()])
    dispatch_executive_plan(tmp_path)
    monkeypatch.setattr(worker.subprocess, "run",
                        lambda command, **kwargs: subprocess.CompletedProcess(
                            command, 0, stdout=json.dumps({
                                "component_count": 3, "available_component_count": 3,
                                "unavailable_components": [], "stale_components": [],
                                "unknown_freshness_components": []
                            }), stderr=""))
    outcome = worker.run_one_department_work(tmp_path)
    assert outcome["state"] == "DONE"
    assert outcome["result_evidence_refs"] == ["runtime:predictive_cloud:status_latest"]


def test_exception_aggregation_keeps_one_owner_per_cause(tmp_path):
    from empire_os.astra_department_dispatch import _owner_incidents
    q = DepartmentWorkQueue(tmp_path)
    for plan in ("x-one", "x-two"):
        q.enqueue_step(plan_id=plan, step=step(step_id="exec_step_repeat"))
        q.block(q.claim_next(), "predictive_cloud_components_unhealthy")
    report = _owner_incidents(q)
    assert report[0]["root_cause"] == "component_freshness_unverified"
    assert report[0]["unresolved_count"] == 2
    assert report[0]["owner_departments"] == ["engineering", "operations_fulfilment"]
    assert report[0]["next_action"] == "refresh_named_source_owners_then_recheck"
