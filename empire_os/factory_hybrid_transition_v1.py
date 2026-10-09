"""Fail-closed engineering work transition advisory for EmpireOS Hybrid V1.

This adapter classifies existing execution-plane and Empire Coder responses.
It must not be used as a completion authority. The worker's DONE and promotion
routes require independently enforced, source-authenticated receipts.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping
from typing import Any

SCHEMA_VERSION = "empire.factory_hybrid_transition.v1"
WAIT = "WAITING_FOR_EVIDENCE"
BLOCK = "BLOCKED"
REPAIR = "REPAIR_REQUIRED"
REVIEW = "READY_FOR_INDEPENDENT_REVIEW"
NOT_APPLICABLE = "NOT_APPLICABLE"

EXECUTION_ADAPTER = "agent_tool_execution_plane"
PLAN_ADAPTER = "empire_coder_plan_bridge"


@dataclass(frozen=True)
class TransitionAssessment:
    request_id: str
    status: str
    reason: str
    proposal_branch: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "request_id": self.request_id,
            "status": self.status,
            "reason": self.reason,
            "proposal_branch": self.proposal_branch,
            "department_work_done": False,
            "production_merge": False,
            "production_deploy": False,
            "external_send": False,
            "payment_action": False,
            "revenue_recognition": False,
            "execution_authority": "none",
        }


def _dict(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def assess_department_builder_result(
    *, department_work_id: str, adapter_result: Mapping[str, Any] | None,
) -> TransitionAssessment:
    """Safely classify an existing department bridge response.

    A candidate can be ready for independent quality review but never DONE.
    In particular, scheduling an IMPLEMENT job is not completing that job,
    and `candidate_gate_passed` is not full factory verification.
    """
    rid = _str(department_work_id)
    result = _dict(adapter_result)
    adapter = _str(result.get("adapter"))
    if not rid:
        return TransitionAssessment(rid, BLOCK, "department_work_identity_missing")
    if adapter not in (EXECUTION_ADAPTER, PLAN_ADAPTER):
        return TransitionAssessment(rid, NOT_APPLICABLE, "non_builder_adapter")
    if result.get("implementation_performed") is not False:
        return TransitionAssessment(rid, BLOCK, "bridge_claims_implementation_completed")
    if result.get("external_execution_performed") is not False:
        return TransitionAssessment(rid, BLOCK, "bridge_claims_external_execution")
    if result.get("execution_authority") != "none":
        return TransitionAssessment(rid, BLOCK, "bridge_claims_execution_authority")

    if adapter == PLAN_ADAPTER:
        if not _str(result.get("coder_task_id")) or not _str(result.get("coder_job_id")):
            return TransitionAssessment(rid, BLOCK, "plan_bridge_missing_job_identity")
        return TransitionAssessment(rid, WAIT, "plan_job_enqueued_not_implemented")

    dispatch = _dict(result.get("dispatch"))
    if _str(dispatch.get("request_id")) != rid:
        return TransitionAssessment(rid, BLOCK, "dispatch_request_identity_mismatch")
    if dispatch.get("production_deploy") is not False:
        return TransitionAssessment(rid, BLOCK, "dispatch_claims_production_deploy")
    if dispatch.get("execution_authority") != "none":
        return TransitionAssessment(rid, BLOCK, "dispatch_claims_execution_authority")
    if any(dispatch.get(field) is not False for field in ("external_send", "payment_action", "revenue_recognition")):
        return TransitionAssessment(rid, BLOCK, "dispatch_claims_consequential_action")

    status = _str(dispatch.get("status"))
    if status in ("BLOCKED", "FAILED", "ERROR", "CANDIDATE_VERIFICATION_FAILED"):
        return TransitionAssessment(rid, REPAIR, "execution_or_verification_failed")
    if status in ("AWAITING_PROMPTFOO", "WAITING_FOR_RUNTIME", "QUEUED"):
        return TransitionAssessment(rid, WAIT, "executor_or_verification_not_finished")

    gate = _dict(dispatch.get("proposal_gate"))
    branch = _str(gate.get("proposal_branch"))
    if status == "CANDIDATE_GATE_PASSED":
        if not branch or gate.get("schema_version") != "empire.execution-plane-candidate-gate.v1":
            return TransitionAssessment(rid, BLOCK, "candidate_gate_identity_missing")
        candidate = _dict(gate.get("candidate_verification"))
        if candidate.get("passed") is not True:
            return TransitionAssessment(rid, REPAIR, "candidate_verification_not_passed", branch)
        if gate.get("candidate_gate_passed") is not True or gate.get("awaiting_promptfoo") is not False:
            return TransitionAssessment(rid, BLOCK, "candidate_gate_state_inconsistent", branch)
        if gate.get("promptfoo_required") is not False:
            return TransitionAssessment(rid, BLOCK, "promptfoo_requirement_inconsistent", branch)
        if gate.get("production_promotion_allowed") is not False or gate.get("execution_authority") != "none":
            return TransitionAssessment(rid, BLOCK, "candidate_gate_claims_authority", branch)
        return TransitionAssessment(rid, REVIEW, "candidate_passed_pending_independent_factory_review", branch)

    return TransitionAssessment(rid, WAIT, "no_verified_candidate_yet", branch)
