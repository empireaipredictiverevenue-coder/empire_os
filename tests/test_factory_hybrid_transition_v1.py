"""Regression tests: candidates and queued jobs must not become DONE."""
import pytest
from empire_os.factory_hybrid_transition_v1 import (
    assess_department_builder_result as judge, BLOCK, REPAIR, WAIT, REVIEW, NOT_APPLICABLE,
)


def plan():
    return dict(adapter="empire_coder_plan_bridge", coder_task_id="t", coder_job_id="j",
                implementation_performed=False, external_execution_performed=False,
                execution_authority="none")


def dispatched(status="CANDIDATE_GATE_PASSED"):
    gate = dict(schema_version="empire.execution-plane-candidate-gate.v1",
                proposal_branch="agent/abc", candidate_verification={"passed":True},
                candidate_gate_passed=True, awaiting_promptfoo=False,
                promptfoo_required=False, production_promotion_allowed=False,
                execution_authority="none")
    return dict(adapter="agent_tool_execution_plane", implementation_performed=False,
                external_execution_performed=False, execution_authority="none",
                dispatch=dict(request_id="work-1", status=status, production_deploy=False,
                              external_send=False, payment_action=False, revenue_recognition=False,
                              execution_authority="none", proposal_gate=gate))


def state(result):
    verdict = judge(department_work_id="work-1", adapter_result=result).as_dict()
    assert verdict["department_work_done"] is False
    assert verdict["production_deploy"] is False
    assert verdict["production_merge"] is False
    assert verdict["execution_authority"] == "none"
    return verdict["status"]


def test_plan_job_not_done():
    assert state(plan()) == WAIT


def test_plan_missing_identity_blocked():
    p=plan(); p["coder_job_id"]=""; assert state(p)==BLOCK


def test_candidate_not_marked_done():
    assert state(dispatched()) == REVIEW


@pytest.mark.parametrize("status", ["QUEUED", "WAITING_FOR_RUNTIME", "AWAITING_PROMPTFOO", "PROPOSAL_READY", "UNKNOWN"])
def test_unfinished_executor_waits(status):
    assert state(dispatched(status)) == WAIT


@pytest.mark.parametrize("status", ["BLOCKED", "FAILED", "ERROR", "CANDIDATE_VERIFICATION_FAILED"])
def test_failed_executor_needs_repair(status):
    assert state(dispatched(status)) == REPAIR


def test_bad_request_identity_blocked():
    p=dispatched(); p["dispatch"]["request_id"]="different"; assert state(p)==BLOCK


def test_false_candidate_pass_repair():
    p=dispatched(); p["dispatch"]["proposal_gate"]["candidate_verification"]["passed"]=False; assert state(p)==REPAIR


def test_missing_gate_blocked():
    p=dispatched(); p["dispatch"]["proposal_gate"]={}; assert state(p)==BLOCK


def test_promptfoo_pending_not_passed():
    p=dispatched(); p["dispatch"]["proposal_gate"].update(promptfoo_required=True,awaiting_promptfoo=True,candidate_gate_passed=False)
    assert state(p)==BLOCK


def test_dispatch_claims_deploy_blocked():
    p=dispatched(); p["dispatch"]["production_deploy"]=True; assert state(p)==BLOCK


def test_bridge_claims_implementation_blocked():
    p=dispatched(); p["implementation_performed"]=True; assert state(p)==BLOCK


def test_unrelated_adapter_not_applicable():
    assert state({"adapter":"contact_identity"}) == NOT_APPLICABLE


def test_bad_type_fail_closed():
    p=dispatched(); p["dispatch"]="bad"; assert state(p)==BLOCK


def test_missing_id_blocked():
    assert judge(department_work_id="",adapter_result=plan()).status==BLOCK


def test_candidate_gate_cannot_claim_authority():
    p=dispatched(); p["dispatch"]["proposal_gate"]["production_promotion_allowed"]=True
    assert state(p)==BLOCK


def test_unknown_adapter_cannot_mark_done():
    assert judge(department_work_id="work-1",adapter_result={"adapter":"unknown"}).as_dict()["department_work_done"] is False


@pytest.mark.parametrize("field", ["external_send", "payment_action", "revenue_recognition"])
def test_dispatch_consequential_flags_must_be_exact_false(field):
    p=dispatched(); p["dispatch"][field]="false"; assert state(p)==BLOCK

def test_dispatch_missing_consequential_field_blocked():
    p=dispatched(); del p["dispatch"]["external_send"]; assert state(p)==BLOCK
