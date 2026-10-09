"""Check real builder-result review intake, without granting completion authority.

The queue's `submit_for_review` method calls this before moving a leased RUNNING
item to REVIEW. This is NOT an independent Judge verdict or a DONE transition.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

SCHEMA = "empire.hybrid_factory_worker_guard.v1"
GATE_SCHEMA = "empire.execution-plane-candidate-gate.v1"


class ReviewIntakeError(ValueError):
    pass


def validate_review_intake(item: Any, result: Mapping[str, Any]) -> None:
    """Raise on anything that is not a verified *candidate awaiting review*."""
    if getattr(item, "target_component", None) != "agent_tool_execution_plane":
        raise ReviewIntakeError("review_intake_not_execution_plane")
    if not isinstance(result, Mapping):
        raise ReviewIntakeError("review_intake_result_invalid")
    hold = result.get("hybrid_factory")
    if not isinstance(hold, Mapping) or hold.get("schema_version") != SCHEMA:
        raise ReviewIntakeError("review_intake_hold_contract_missing")
    if hold.get("enforced") is not True or hold.get("department_work_done") is not False:
        raise ReviewIntakeError("review_intake_hold_not_enforced")
    if hold.get("disposition") != "READY_FOR_INDEPENDENT_REVIEW":
        raise ReviewIntakeError("review_intake_wrong_disposition")
    if hold.get("request_id") != getattr(item, "id", None):
        raise ReviewIntakeError("review_intake_work_identity_mismatch")
    if result.get("adapter") != "agent_tool_execution_plane":
        raise ReviewIntakeError("review_intake_adapter_mismatch")
    if (result.get("implementation_performed") is not False
            or result.get("external_execution_performed") is not False
            or result.get("execution_authority") != "none"):
        raise ReviewIntakeError("review_intake_bridge_claims_authority")
    dispatch = result.get("dispatch")
    if not isinstance(dispatch, Mapping):
        raise ReviewIntakeError("review_intake_dispatch_missing")
    if dispatch.get("request_id") != getattr(item, "id", None):
        raise ReviewIntakeError("review_intake_dispatch_identity_mismatch")
    if dispatch.get("status") != "CANDIDATE_GATE_PASSED":
        raise ReviewIntakeError("review_intake_dispatch_not_verified_candidate")
    for key in ("production_deploy", "external_send", "payment_action", "revenue_recognition"):
        if dispatch.get(key) is not False:
            raise ReviewIntakeError("review_intake_consequential_action_claim")
    if dispatch.get("execution_authority") != "none":
        raise ReviewIntakeError("review_intake_dispatch_claims_authority")
    gate = dispatch.get("proposal_gate")
    if not isinstance(gate, Mapping) or gate.get("schema_version") != GATE_SCHEMA:
        raise ReviewIntakeError("review_intake_candidate_gate_missing")
    if (not isinstance(gate.get("proposal_branch"), str)
            or not gate["proposal_branch"].strip()
            or gate.get("candidate_gate_passed") is not True
            or gate.get("promptfoo_required") is not False
            or gate.get("awaiting_promptfoo") is not False
            or gate.get("production_promotion_allowed") is not False
            or gate.get("execution_authority") != "none"):
        raise ReviewIntakeError("review_intake_candidate_gate_invalid")
    candidate = gate.get("candidate_verification")
    if not isinstance(candidate, Mapping) or candidate.get("passed") is not True:
        raise ReviewIntakeError("review_intake_deterministic_verification_not_passed")
