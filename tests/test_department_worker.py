import json
import subprocess

import empire_os.department_worker as worker_module
from empire_os.astra_department_dispatch import dispatch_executive_plan
from empire_os.astra_department_evaluator import evaluate_executive_plan
from empire_os.department_work_queue import DepartmentWorkQueue


def _step(**overrides):
    row = {
        "step_id": "exec_step_product",
        "goal_key": "complete_opportunity_evidence",
        "department_keys": ["product"],
        "target_component": "commercial_product_catalog",
        "action": "resolve_verified_price_cost_and_margin_basis",
        "authority": "internal_write",
        "auto_dispatch_eligible": True,
        "founder_gate_required": False,
        "intelligence_request": {
            "task": "reasoning",
            "resolve_via": "intelligence_router",
        },
        "memory_query": {"retrieval_only": True},
        "evidence_refs": ["opportunity:1"],
        "success_condition": "economics resolved or remains unknown",
        "rationale": "missing margin evidence",
    }
    row.update(overrides)
    return row


def _write_plan(root, steps):
    path = root / "runtime/astra/executive_latest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "plan_id": "astra_plan_test",
        "plan": steps,
    }))


def test_safe_worker_executes_allowlisted_internal_adapter(
    tmp_path, monkeypatch
):
    _write_plan(tmp_path, [_step()])
    dispatch = dispatch_executive_plan(tmp_path)
    assert dispatch["queued_count"] == 1

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            0,
            stdout='{"ok": true}',
            stderr="",
        )

    monkeypatch.setattr(worker_module.subprocess, "run", fake_run)
    result = worker_module.run_one_department_work(tmp_path)

    assert result["state"] == "DONE"
    assert result["target_component"] == "commercial_product_catalog"
    assert result["execution_authority"] == "none"
    queue = DepartmentWorkQueue(tmp_path)
    assert queue.counts()["done"] == 1


def test_unsupported_adapter_is_blocked_not_completed(tmp_path):
    _write_plan(tmp_path, [
        _step(
            step_id="exec_step_predictive",
            department_keys=["data_quant"],
            target_component="predictive_intelligence",
            action="resolve_quant_input:probability_success",
            authority="observe",
        )
    ])
    dispatch_executive_plan(tmp_path)
    result = worker_module.run_one_department_work(tmp_path)

    assert result["state"] == "BLOCKED"
    assert result["blocker"] == "specialist_adapter_required"
    queue = DepartmentWorkQueue(tmp_path)
    assert queue.counts()["blocked"] == 1
    assert queue.counts()["done"] == 0


def test_evaluator_tracks_done_and_blocked_work(tmp_path, monkeypatch):
    _write_plan(tmp_path, [
        _step(),
        _step(
            step_id="exec_step_predictive",
            department_keys=["data_quant"],
            target_component="predictive_intelligence",
            action="resolve_quant_input:probability_success",
            authority="observe",
        ),
    ])
    dispatch_executive_plan(tmp_path)

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="ok",
            stderr="",
        )

    monkeypatch.setattr(worker_module.subprocess, "run", fake_run)
    worker_module.run_department_worker(tmp_path, max_items=4)

    result = evaluate_executive_plan(tmp_path)
    assert result["eligible_step_count"] == 2
    assert result["status_counts"]["DONE"] == 1
    assert result["status_counts"]["BLOCKED"] == 1
    assert result["evaluation_state"] == "BLOCKED"
    assert result["plan_success_claimed"] is False
    assert result["execution_authority"] == "none"
