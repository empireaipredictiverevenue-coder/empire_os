"""Phase 3 agent work completion guard regression tests."""
from __future__ import annotations

import pytest
from empire_os.factory_hybrid_worker_guard_v1 import guard_department_bridge


def bridge(status="QUEUED", *, worker="empire_coder"):
    gate = dict(schema_version="empire.execution-plane-candidate-gate.v1",
                proposal_branch="proposal/safe-01",
                candidate_verification={"passed": True},
                candidate_gate_passed=True, awaiting_promptfoo=False,
                promptfoo_required=False, production_promotion_allowed=False,
                execution_authority="none")
    return dict(adapter="agent_tool_execution_plane", implementation_performed=False,
                external_execution_performed=False, execution_authority="none",
                dispatch=dict(request_id="work-1", worker=worker, status=status,
                              production_deploy=False, external_send=False,
                              payment_action=False, revenue_recognition=False,
                              execution_authority="none", proposal_gate=gate))


def assess(result, *, capability="backend_code", component="agent_tool_execution_plane"):
    return guard_department_bridge(work_id="work-1", target_component=component,
                                   intelligence_request={"execution_plane": {"capability": capability}},
                                   result=result)


def assert_held(verdict, expected):
    assert verdict.enforced is True
    assert verdict.disposition == expected
    data = verdict.as_dict()
    assert data["department_work_done"] is False
    assert data["engineering_verified"] is False
    assert data["production_merge"] is False
    assert data["production_deploy"] is False
    assert data["execution_authority"] == "none"


@pytest.mark.parametrize("capability", [
    "backend_code", "parallel_backend_code", "frontend_code", "refactor", "tests", "documentation",
])
def test_engineering_capabilities_held(capability):
    assert_held(assess(bridge(worker="pi"), capability=capability), "WAITING_FOR_EVIDENCE")


@pytest.mark.parametrize("status,expected", [
    ("QUEUED", "WAITING_FOR_EVIDENCE"),
    ("AWAITING_PROMPTFOO", "WAITING_FOR_EVIDENCE"),
    ("CANDIDATE_GATE_PASSED", "READY_FOR_INDEPENDENT_REVIEW"),
    ("FAILED", "REPAIR_REQUIRED"),
    ("BLOCKED", "REPAIR_REQUIRED"),
])
def test_no_dispatch_or_candidate_state_can_be_done(status, expected):
    assert_held(assess(bridge(status)), expected)


def test_plan_enqueue_is_not_implementation():
    plan = dict(adapter="empire_coder_plan_bridge", coder_task_id="task-1", coder_job_id="job-1",
                implementation_performed=False, external_execution_performed=False, execution_authority="none")
    assert_held(assess(plan, component="empire_coder"), "WAITING_FOR_EVIDENCE")


def test_dispatch_wrong_request_identity_blocks():
    result = bridge(); result["dispatch"]["request_id"] = "another-task"
    assert_held(assess(result), "BLOCKED")


def test_builder_claim_of_completed_work_blocks():
    result = bridge(); result["implementation_performed"] = True
    assert_held(assess(result), "BLOCKED")


def test_builder_cannot_claim_deployment():
    result = bridge(); result["dispatch"]["production_deploy"] = True
    assert_held(assess(result), "BLOCKED")


def test_malformed_bridge_blocks():
    assert_held(assess({}), "BLOCKED")


def test_missing_capability_is_held():
    assert_held(assess(bridge(worker=""), capability=""), "WAITING_FOR_EVIDENCE")


def test_nonengineering_capability_without_builder_witness_unchanged():
    result = dict(adapter="agent_tool_execution_plane", dispatch=dict(status="QUEUED"),
                  implementation_performed=False, external_execution_performed=False, execution_authority="none")
    verdict = assess(result, capability="sensor_observe")
    assert verdict.enforced is False
    assert verdict.disposition == "NOT_APPLICABLE"


def test_nonengineering_adapter_unchanged():
    verdict = assess({"adapter": "anything"}, component="identity_enrichment")
    assert verdict.enforced is False
