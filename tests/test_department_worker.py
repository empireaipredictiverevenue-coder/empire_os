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


def test_predictive_adapter_blocks_when_verified_cohort_is_insufficient(
    tmp_path, monkeypatch
):
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

    monkeypatch.setattr(
        worker_module,
        "refresh_predictive_intelligence",
        lambda *args, **kwargs: {
            "source_outcome_count": 5,
            "matched_outcome_count": 5,
            "probability_ready_product_count": 0,
            "timing_ready_product_count": 0,
            "reused_existing_snapshot": False,
            "product_estimates": {
                "managed_service": {
                    "probability_available": False,
                    "probability_success": None,
                    "confidence": None,
                    "uncertainty": None,
                    "time_to_revenue_available": False,
                    "time_to_revenue_days": None,
                }
            },
        },
    )
    result = worker_module.run_one_department_work(tmp_path)

    assert result["state"] == "BLOCKED"
    assert result["blocker"] == "insufficient_verified_outcome_cohort"
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
    monkeypatch.setattr(
        worker_module,
        "refresh_predictive_intelligence",
        lambda *args, **kwargs: {
            "source_outcome_count": 5,
            "matched_outcome_count": 5,
            "probability_ready_product_count": 0,
            "timing_ready_product_count": 0,
            "reused_existing_snapshot": False,
            "product_estimates": {},
        },
    )
    worker_module.run_department_worker(tmp_path, max_items=4)

    result = evaluate_executive_plan(tmp_path)
    assert result["eligible_step_count"] == 2
    assert result["status_counts"]["DONE"] == 1
    assert result["status_counts"]["BLOCKED"] == 1
    assert result["evaluation_state"] == "BLOCKED"
    assert result["plan_success_claimed"] is False
    assert result["execution_authority"] == "none"


def test_predictive_adapter_completes_only_supported_field(
    tmp_path, monkeypatch
):
    _write_plan(tmp_path, [
        _step(
            step_id="exec_step_predictive_ready",
            department_keys=["data_quant"],
            target_component="predictive_intelligence",
            action="resolve_quant_input:probability_success",
            authority="observe",
        )
    ])
    dispatch_executive_plan(tmp_path)
    monkeypatch.setattr(
        worker_module,
        "refresh_predictive_intelligence",
        lambda *args, **kwargs: {
            "source_outcome_count": 30,
            "matched_outcome_count": 30,
            "probability_ready_product_count": 1,
            "timing_ready_product_count": 0,
            "reused_existing_snapshot": False,
            "product_estimates": {
                "managed_service": {
                    "probability_available": True,
                    "probability_success": 0.58,
                    "confidence": 0.64,
                    "uncertainty": 0.18,
                    "time_to_revenue_available": False,
                    "time_to_revenue_days": None,
                }
            },
        },
    )
    result = worker_module.run_one_department_work(tmp_path)
    assert result["state"] == "DONE"
    assert result["target_component"] == "predictive_intelligence"
    assert "runtime:predictive_intelligence:latest" in result[
        "result_evidence_refs"
    ]


def test_identity_adapter_completes_for_targeted_entity(
    tmp_path, monkeypatch
):
    _write_plan(tmp_path, [
        _step(
            step_id="exec_step_identity",
            department_keys=["sales_revenue"],
            target_component="identity_enrichment",
            action="verify_decision_maker",
            authority="internal_write",
            evidence_refs=["buyer_state:entity-123"],
        )
    ])
    dispatch_executive_plan(tmp_path)
    monkeypatch.setattr(
        worker_module,
        "resolve_entity_decision_maker",
        lambda **kwargs: {
            "status": "AVAILABLE",
            "entity_id": "entity-123",
            "prospect_id": "prospect-1",
            "decision_maker": {
                "name": "Alex Smith",
                "title": "Owner",
            },
            "new_identity_persisted": True,
            "evidence_refs": [
                "canonical:prospects:prospect-1",
            ],
            "outreach_executed": False,
            "execution_authority": "none",
        },
    )
    result = worker_module.run_one_department_work(tmp_path)
    assert result["state"] == "DONE"
    assert result["target_component"] == "identity_enrichment"
    assert result["result_evidence_refs"] == [
        "canonical:prospects:prospect-1"
    ]


def test_identity_adapter_blocks_when_target_unresolved(
    tmp_path, monkeypatch
):
    _write_plan(tmp_path, [
        _step(
            step_id="exec_step_identity_blocked",
            department_keys=["sales_revenue"],
            target_component="identity_enrichment",
            action="verify_decision_maker",
            authority="internal_write",
            evidence_refs=["buyer_state:entity-123"],
        )
    ])
    dispatch_executive_plan(tmp_path)
    monkeypatch.setattr(
        worker_module,
        "resolve_entity_decision_maker",
        lambda **kwargs: {
            "status": "UNAVAILABLE",
            "entity_id": "entity-123",
            "reason": "decision_maker_not_resolved_from_bounded_evidence",
            "evidence_refs": [],
            "outreach_executed": False,
            "execution_authority": "none",
        },
    )
    result = worker_module.run_one_department_work(tmp_path)
    assert result["state"] == "BLOCKED"
    assert result["blocker"] == (
        "decision_maker_not_resolved_from_bounded_evidence"
    )



def test_execution_plane_department_adapter_dispatches_explicit_contract(
    tmp_path, monkeypatch
):
    _write_plan(tmp_path, [
        _step(
            step_id="exec_step_execution_plane",
            department_keys=["engineering"],
            target_component="agent_tool_execution_plane",
            action="build_bounded_feature",
            authority="internal_write",
            intelligence_request={
                "execution_plane": {
                    "capability": "backend_code",
                    "objective": "Implement bounded feature.",
                    "allowed_paths": ["empire_os/example.py"],
                    "lease_resources": ["domain:example"],
                    "required_tests": ["tests/test_example.py"],
                    "execute_pi": False,
                }
            },
        )
    ])
    dispatch_executive_plan(tmp_path)

    captured = {}

    def fake_dispatch(root, request, execute_pi=True):
        captured["root"] = root
        captured["request"] = request
        captured["execute_pi"] = execute_pi
        return {
            "status": "QUEUED",
            "worker": "hermes",
            "execution_authority": "none",
        }

    monkeypatch.setattr(
        worker_module,
        "dispatch_execution_request",
        fake_dispatch,
    )
    result = worker_module.run_one_department_work(tmp_path)

    assert result["state"] == "DONE"
    assert result["target_component"] == "agent_tool_execution_plane"
    assert captured["request"].capability == "backend_code"
    assert captured["request"].allowed_paths == ("empire_os/example.py",)
    assert captured["request"].lease_resources == ("domain:example",)
    assert captured["execute_pi"] is False


def test_execution_plane_department_adapter_fails_without_contract(tmp_path):
    _write_plan(tmp_path, [
        _step(
            step_id="exec_step_execution_plane_bad",
            department_keys=["engineering"],
            target_component="agent_tool_execution_plane",
            action="build_unspecified_feature",
            authority="internal_write",
            intelligence_request={},
        )
    ])
    dispatch_executive_plan(tmp_path)

    result = worker_module.run_one_department_work(tmp_path)
    assert result["state"] == "FAILED"
    assert "execution_plane contract required" in result["error"]
