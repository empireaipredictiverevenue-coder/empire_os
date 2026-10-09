"""Hybrid Factory V1 Phase 3: fail-closed department engineering completion hold.

This module is deliberately not an approval authority. It only prevents a
planning/dispatch/candidate milestone being represented as completed engineering.
It does not trust or load agent-provided approval JSON.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from empire_os.factory_hybrid_transition_v1 import (
    assess_department_builder_result,
    WAIT, REVIEW, REPAIR, BLOCK,
)

SCHEMA = "empire.hybrid_factory_worker_guard.v1"

# These are scoped to the worker's existing implementation capabilities; the
# real execution-plane routing policy remains the authority over what can run.
ENGINEERING_CAPABILITIES = frozenset({
    "backend_code", "parallel_backend_code", "frontend_code", "refactor",
    "tests", "documentation",
})
BUILDER_WORKERS = frozenset({"pi", "hermes", "empire_coder"})
CANDIDATE_STATES = frozenset({
    "CANDIDATE_GATE_PASSED", "AWAITING_PROMPTFOO", "PROPOSAL_READY",
    "CANDIDATE_VERIFICATION_FAILED",
})


@dataclass(frozen=True)
class HoldDecision:
    enforced: bool
    disposition: str
    reason: str
    request_id: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA,
            "enforced": self.enforced,
            "disposition": self.disposition,
            "reason": self.reason,
            "request_id": self.request_id,
            "engineering_verified": False,
            "department_work_done": False if self.enforced else None,
            "production_merge": False,
            "production_deploy": False,
            "external_send": False,
            "payment_action": False,
            "revenue_recognition": False,
            "execution_authority": "none",
        }


def _map(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def guard_department_bridge(
    *, work_id: str, target_component: str,
    intelligence_request: Mapping[str, Any] | None,
    result: Mapping[str, Any] | None,
) -> HoldDecision:
    """Return a hold for builder engineering transitions; never return PASS.

    "enforced=False" means a non-engineering adapter retains its existing
    semantics. ``enforced=True`` is a HOLD (including for candidate gates that
    passed deterministic tests) until a future trusted independent finalizer.
    """
    work_id = work_id.strip() if isinstance(work_id, str) else ""
    component = target_component.strip() if isinstance(target_component, str) else ""
    request = _map(intelligence_request)
    bridge = _map(result)
    if component == "empire_coder":
        enforced = True
    elif component == "agent_tool_execution_plane":
        contract = _map(request.get("execution_plane"))
        capability = contract.get("capability")
        capability = capability.strip() if isinstance(capability, str) else ""
        dispatch = _map(bridge.get("dispatch"))
        worker = dispatch.get("worker")
        worker = worker.strip() if isinstance(worker, str) else ""
        routing = _map(dispatch.get("route"))
        route_worker = routing.get("worker_key")
        route_worker = route_worker.strip() if isinstance(route_worker, str) else ""
        state = dispatch.get("status")
        state = state.strip().upper() if isinstance(state, str) else ""
        enforced = (
            not capability
            or capability in ENGINEERING_CAPABILITIES
            or worker in BUILDER_WORKERS
            or route_worker in BUILDER_WORKERS
            or bool(dispatch.get("proposal_gate"))
            or state in CANDIDATE_STATES
        )
    else:
        enforced = False
    if not enforced:
        return HoldDecision(False, "NOT_APPLICABLE", "non_engineering_adapter_unchanged", work_id)
    assessment = assess_department_builder_result(
        department_work_id=work_id, adapter_result=bridge,
    )
    state = assessment.status
    if state not in {WAIT, REVIEW, REPAIR, BLOCK}:
        # Unknown / malformed assessment must never grant completion.
        return HoldDecision(True, BLOCK, "unrecognized_engineering_bridge_result", work_id)
    return HoldDecision(True, state, assessment.reason, work_id)
