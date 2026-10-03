from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from empire_os.hybrid_compute import (
    HybridRequest,
    Route,
    recommend_route,
)
from empire_os.node_registry import NodeRegistry


BRIDGE_VERSION = "empire-hybrid-node-bridge-v1"


ROUTE_CAPABILITIES = {
    Route.LOCAL_SMALL: "compute.local.small",
    Route.LOCAL_STRONG: "compute.local.strong",
    Route.FRONTIER: "compute.frontier",
    Route.PREDICTIVE: "compute.predictive",
    Route.DETERMINISTIC: "compute.deterministic",
    Route.HUMAN_GATE: "governance.human",
}


@dataclass(frozen=True)
class NodeExecutionPlan:
    route: Route
    required_capability: str
    candidate_node_ids: tuple[str, ...]
    can_execute: bool
    requires_approval: bool
    fail_closed: bool
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "bridge_version": BRIDGE_VERSION,
            "route": self.route.value,
            "required_capability": (
                self.required_capability
            ),
            "candidate_node_ids": list(
                self.candidate_node_ids
            ),
            "candidate_count": len(
                self.candidate_node_ids
            ),
            "can_execute": self.can_execute,
            "requires_approval": (
                self.requires_approval
            ),
            "fail_closed": self.fail_closed,
            "reason_codes": list(self.reason_codes),
            "production_authority": False,
        }


def plan_node_execution(
    request: HybridRequest,
    registry: NodeRegistry,
) -> NodeExecutionPlan:
    decision = recommend_route(request)

    capability = ROUTE_CAPABILITIES[
        decision.recommended_route
    ]

    candidates = registry.candidates(
        capability=capability,
        route=decision.recommended_route,
        tenant_id=request.tenant_id,
    )

    reasons = list(decision.reason_codes)

    if not candidates:
        reasons.append("no_healthy_capability_node")

    if decision.requires_approval:
        reasons.append("approval_boundary_preserved")

    # V1 bridge is deliberately planning-only.
    return NodeExecutionPlan(
        route=decision.recommended_route,
        required_capability=capability,
        candidate_node_ids=tuple(
            node.node_id for node in candidates
        ),
        can_execute=False,
        requires_approval=decision.requires_approval,
        fail_closed=not bool(candidates),
        reason_codes=tuple(reasons),
    )
