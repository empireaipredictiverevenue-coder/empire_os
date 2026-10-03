from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping


ROUTER_VERSION = "empire-hybrid-compute-v1"
ROUTER_MODE = "observe"


class Route(str, Enum):
    LOCAL_SMALL = "local_small"
    LOCAL_STRONG = "local_strong"
    FRONTIER = "frontier"
    PREDICTIVE = "predictive"
    DETERMINISTIC = "deterministic"
    OPTIMIZATION = "optimization"
    HUMAN_GATE = "human_gate"


class Sensitivity(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class TaskKind(str, Enum):
    CLASSIFY = "classify"
    EXTRACT = "extract"
    SUMMARISE = "summarise"
    REASON = "reason"
    RESEARCH = "research"
    PREDICTIVE_REVENUE = "predictive_revenue"
    QUANT = "quant"
    OPTIMIZE = "optimize"
    OUTBOUND_DRAFT = "outbound_draft"
    OUTBOUND_SEND = "outbound_send"
    COMMERCIAL_BINDING = "commercial_binding"
    PAYMENT = "payment"
    INFRASTRUCTURE_CHANGE = "infrastructure_change"
    UNKNOWN = "unknown"


_GOVERNED_ACTIONS = {
    TaskKind.OUTBOUND_SEND,
    TaskKind.COMMERCIAL_BINDING,
    TaskKind.PAYMENT,
    TaskKind.INFRASTRUCTURE_CHANGE,
}


@dataclass(frozen=True)
class HybridRequest:
    task_kind: TaskKind
    sensitivity: Sensitivity = Sensitivity.INTERNAL
    complexity: float = 0.5
    risk: float = 0.2
    quality_floor: float = 0.85
    max_latency_ms: int | None = None
    expected_value_gbp: float = 0.0
    requires_external_knowledge: bool = False
    current_route: Route | None = None
    tenant_id: str | None = None
    context_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("complexity", "risk", "quality_floor"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")

        if self.max_latency_ms is not None and self.max_latency_ms <= 0:
            raise ValueError("max_latency_ms must be positive")

        if self.expected_value_gbp < 0:
            raise ValueError("expected_value_gbp must be >= 0")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "HybridRequest":
        return cls(
            task_kind=TaskKind(
                str(raw.get("task_kind", TaskKind.UNKNOWN.value))
            ),
            sensitivity=Sensitivity(
                str(
                    raw.get(
                        "sensitivity",
                        Sensitivity.INTERNAL.value,
                    )
                )
            ),
            complexity=float(raw.get("complexity", 0.5)),
            risk=float(raw.get("risk", 0.2)),
            quality_floor=float(raw.get("quality_floor", 0.85)),
            max_latency_ms=(
                int(raw["max_latency_ms"])
                if raw.get("max_latency_ms") is not None
                else None
            ),
            expected_value_gbp=float(
                raw.get("expected_value_gbp", 0.0)
            ),
            requires_external_knowledge=bool(
                raw.get("requires_external_knowledge", False)
            ),
            current_route=(
                Route(str(raw["current_route"]))
                if raw.get("current_route") is not None
                else None
            ),
            tenant_id=raw.get("tenant_id"),
            context_id=raw.get("context_id"),
        )


@dataclass(frozen=True)
class HybridDecision:
    recommended_route: Route
    policy_version: str
    mode: str
    can_execute: bool
    requires_approval: bool
    frontier_allowed: bool
    reason_codes: tuple[str, ...]
    current_route: Route | None
    route_changed: bool | None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)

        payload["recommended_route"] = (
            self.recommended_route.value
        )
        payload["current_route"] = (
            self.current_route.value
            if self.current_route
            else None
        )
        payload["reason_codes"] = list(
            self.reason_codes
        )

        return payload


def recommend_route(
    request: HybridRequest,
) -> HybridDecision:
    reasons: list[str] = []

    frontier_allowed = request.sensitivity in {
        Sensitivity.PUBLIC,
        Sensitivity.INTERNAL,
    }

    requires_approval = (
        request.task_kind in _GOVERNED_ACTIONS
    )

    if requires_approval:
        route = Route.DETERMINISTIC
        reasons.extend(
            (
                "governed_action",
                "authority_separate_from_compute",
            )
        )

    elif (
        request.task_kind
        is TaskKind.PREDICTIVE_REVENUE
    ):
        route = Route.PREDICTIVE
        reasons.append("predictive_workload")

    elif request.task_kind is TaskKind.QUANT:
        route = Route.DETERMINISTIC
        reasons.append("deterministic_quant_workload")

    elif request.task_kind is TaskKind.OPTIMIZE:
        route = Route.OPTIMIZATION
        reasons.append("optimization_workload")

    elif (
        request.requires_external_knowledge
        and request.sensitivity
        is Sensitivity.RESTRICTED
    ):
        route = Route.HUMAN_GATE
        reasons.extend(
            (
                "restricted_data",
                "external_knowledge_conflict",
                "fail_closed",
            )
        )

    elif request.task_kind in {
        TaskKind.CLASSIFY,
        TaskKind.EXTRACT,
    }:
        if (
            request.quality_floor >= 0.97
            or request.complexity >= 0.70
        ):
            route = Route.LOCAL_STRONG
            reasons.append(
                "quality_or_complexity_requires_stronger_local"
            )
        else:
            route = Route.LOCAL_SMALL
            reasons.append(
                "bounded_high_volume_workload"
            )

    elif (
        request.max_latency_ms is not None
        and request.max_latency_ms <= 500
    ):
        if request.complexity < 0.65:
            route = Route.LOCAL_SMALL
            reasons.append(
                "tight_latency_budget"
            )
        else:
            route = Route.LOCAL_STRONG
            reasons.append(
                "tight_latency_with_complexity"
            )

    elif (
        request.requires_external_knowledge
        and frontier_allowed
    ):
        route = Route.FRONTIER
        reasons.append(
            "external_knowledge_required"
        )

    elif (
        frontier_allowed
        and request.quality_floor >= 0.90
        and (
            request.complexity >= 0.75
            or request.expected_value_gbp
            >= 10_000
        )
    ):
        route = Route.FRONTIER
        reasons.append(
            "high_value_or_complex_reasoning"
        )

    elif request.sensitivity in {
        Sensitivity.CONFIDENTIAL,
        Sensitivity.RESTRICTED,
    }:
        route = Route.LOCAL_STRONG
        reasons.append(
            "sensitive_context_local_preference"
        )

    elif request.task_kind is TaskKind.RESEARCH:
        route = (
            Route.FRONTIER
            if frontier_allowed
            else Route.LOCAL_STRONG
        )
        reasons.append("research_workload")

    else:
        route = Route.LOCAL_STRONG
        reasons.append(
            "default_strong_local"
        )

    if not frontier_allowed:
        reasons.append(
            "frontier_blocked_by_sensitivity"
        )

    if (
        request.risk >= 0.80
        and route
        not in {
            Route.DETERMINISTIC,
            Route.HUMAN_GATE,
        }
    ):
        reasons.append(
            "high_risk_requires_downstream_governance"
        )

    route_changed = (
        None
        if request.current_route is None
        else route is not request.current_route
    )

    return HybridDecision(
        recommended_route=route,
        policy_version=ROUTER_VERSION,
        mode=ROUTER_MODE,
        can_execute=False,
        requires_approval=requires_approval,
        frontier_allowed=frontier_allowed,
        reason_codes=tuple(reasons),
        current_route=request.current_route,
        route_changed=route_changed,
    )


def evaluate_mapping(
    raw: Mapping[str, Any],
) -> dict[str, Any]:
    request = HybridRequest.from_mapping(raw)
    decision = recommend_route(request)

    return {
        "router": {
            "policy_version": ROUTER_VERSION,
            "mode": ROUTER_MODE,
            "production_authority": False,
        },
        "request": {
            "task_kind": request.task_kind.value,
            "sensitivity": request.sensitivity.value,
            "complexity": request.complexity,
            "risk": request.risk,
            "quality_floor": request.quality_floor,
            "max_latency_ms": request.max_latency_ms,
            "expected_value_gbp": (
                request.expected_value_gbp
            ),
            "requires_external_knowledge": (
                request.requires_external_knowledge
            ),
            "current_route": (
                request.current_route.value
                if request.current_route
                else None
            ),
            "tenant_id": request.tenant_id,
            "context_id": request.context_id,
        },
        "decision": decision.to_dict(),
    }


def main() -> int:
    try:
        raw = json.load(sys.stdin)

        if not isinstance(raw, dict):
            raise ValueError(
                "stdin JSON must be an object"
            )

        print(
            json.dumps(
                evaluate_mapping(raw),
                sort_keys=True,
            )
        )
        return 0

    except (
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ) as exc:
        print(
            json.dumps(
                {
                    "router": {
                        "policy_version": (
                            ROUTER_VERSION
                        ),
                        "mode": ROUTER_MODE,
                        "production_authority": (
                            False
                        ),
                    },
                    "error": str(exc),
                    "fail_closed": True,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
