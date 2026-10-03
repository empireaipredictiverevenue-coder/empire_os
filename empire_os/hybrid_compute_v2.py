"""Empire Hybrid Compute V2 shadow control plane.

This module observes canonical EmpireOS model inventory, health and routing.
It never executes an LLM route and never grants production authority.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from empire_os.hybrid_compute import (
    HybridRequest,
    Route,
    TaskKind,
    recommend_route,
)
from empire_os.model_health import ModelHealth
from empire_os.model_registry import ModelRegistry
from empire_os.model_router import ModelRouter
from empire_os.telemetry import (
    TelemetrySink,
    emit_event,
    new_trace_context,
)


SCHEMA_VERSION = "empire.hybrid_compute.shadow.v2"
MODE = "observe"


_TASK_MAP: dict[TaskKind, str] = {
    TaskKind.CLASSIFY: "classification",
    TaskKind.EXTRACT: "extraction",
    TaskKind.SUMMARISE: "summarization",
    TaskKind.REASON: "reasoning",
    TaskKind.RESEARCH: "research",
    TaskKind.PREDICTIVE_REVENUE: "predictive_revenue",
    TaskKind.QUANT: "quantitative_research",
    TaskKind.OPTIMIZE: "optimization",
    TaskKind.OUTBOUND_DRAFT: "reasoning",
    TaskKind.OUTBOUND_SEND: "reasoning",
    TaskKind.COMMERCIAL_BINDING: "reasoning",
    TaskKind.PAYMENT: "reasoning",
    TaskKind.INFRASTRUCTURE_CHANGE: "reasoning",
    TaskKind.UNKNOWN: "reasoning",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _attribute(
    value: Any,
    *names: str,
) -> Any:
    for name in names:
        if hasattr(value, name):
            candidate = getattr(value, name)
            if candidate is not None:
                return candidate

    if isinstance(value, Mapping):
        for name in names:
            if name in value and value[name] is not None:
                return value[name]

    return None


def _text(value: Any) -> str | None:
    if value is None:
        return None

    rendered = str(value).strip()
    return rendered or None


def _float(value: Any) -> float | None:
    if value is None:
        return None

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    if result != result:
        return None

    return result


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value

    return None


def _model_id(spec: Any) -> str:
    value = _attribute(
        spec,
        "model_id",
        "id",
        "model",
        "name",
    )

    if value is None:
        return "unknown"

    return str(value)


def _provider(spec: Any) -> str | None:
    return _text(
        _attribute(
            spec,
            "provider",
            "provider_id",
            "provider_key",
        )
    )


_LOCAL_DEPLOYMENTS = frozenset(
    {
        "local",
        "on_device",
        "on-device",
        "on_prem",
        "on-prem",
        "self_hosted",
        "self-hosted",
        "edge",
    }
)

_REMOTE_DEPLOYMENTS = frozenset(
    {
        "remote",
        "cloud",
        "hosted",
        "api",
        "saas",
    }
)


def _deployment(spec: Any) -> str | None:
    value = _text(
        _attribute(
            spec,
            "deployment",
            "deployment_type",
        )
    )

    return value.lower() if value else None


def _is_local(spec: Any) -> bool | None:
    explicit = _bool(
        _attribute(
            spec,
            "local",
            "is_local",
        )
    )

    if explicit is not None:
        return explicit

    deployment = _deployment(spec)

    if deployment in _LOCAL_DEPLOYMENTS:
        return True

    if deployment in _REMOTE_DEPLOYMENTS:
        return False

    return None


def _model_name(spec: Any) -> str | None:
    return _text(
        _attribute(
            spec,
            "model",
            "model_name",
        )
    )


def _route_model_spec(route: Any) -> Any | None:
    explicit = _attribute(
        route,
        "model_spec",
        "spec",
    )

    if explicit is not None:
        return explicit

    candidate = getattr(route, "model", None)

    if candidate is None:
        return None

    if isinstance(
        candidate,
        (str, int, float, bool),
    ):
        return None

    if isinstance(candidate, Mapping):
        if any(
            key in candidate
            for key in (
                "model_id",
                "provider",
                "deployment",
            )
        ):
            return candidate

        return None

    return candidate


def _quality_for(
    spec: Any,
    task: str,
) -> float | None:
    method = getattr(spec, "quality_for", None)

    if not callable(method):
        return None

    try:
        return _float(method(task))
    except Exception:
        return None


def _cost_known(spec: Any) -> bool | None:
    method = getattr(spec, "cost_known", None)

    if not callable(method):
        return None

    try:
        result = method()
    except Exception:
        return None

    return result if isinstance(result, bool) else None


def _capabilities(spec: Any) -> list[str]:
    raw = _attribute(
        spec,
        "capabilities",
        "capability",
    )

    if raw is None:
        return []

    if isinstance(raw, str):
        return [raw]

    if isinstance(raw, (set, tuple, list)):
        return sorted(
            str(value)
            for value in raw
            if str(value).strip()
        )

    return []


def _candidate_observation(
    spec: Any,
    *,
    task: str,
) -> dict[str, Any]:
    return {
        "model_id": _model_id(spec),
        "model": (
            _model_name(spec)
            or _model_id(spec)
        ),
        "provider": _provider(spec),
        "deployment": _deployment(spec),
        "local": _is_local(spec),
        "quality": _quality_for(spec, task),
        "cost_known": _cost_known(spec),
        "capabilities": _capabilities(spec),
    }


def build_capability_view(
    *,
    registry: ModelRegistry,
    task: str,
) -> dict[str, Any]:
    """Read the canonical registry without altering it."""

    try:
        all_models = list(registry.all())
        candidates = list(
            registry.candidates(task=task)
        )
    except Exception as exc:
        return {
            "status": "UNAVAILABLE",
            "reason": "canonical_registry_read_failed",
            "error_class": type(exc).__name__,
            "all_model_count": None,
            "candidate_count": None,
            "candidates": [],
        }

    rows = [
        _candidate_observation(
            spec,
            task=task,
        )
        for spec in candidates
    ]

    return {
        "status": "AVAILABLE",
        "all_model_count": len(all_models),
        "candidate_count": len(rows),
        "local_candidate_count": sum(
            row["local"] is True
            for row in rows
        ),
        "remote_candidate_count": sum(
            row["local"] is False
            for row in rows
        ),
        "unknown_placement_count": sum(
            row["local"] is None
            for row in rows
        ),
        "candidates": rows,
    }


def build_health_view(
    *,
    health: ModelHealth,
) -> dict[str, Any]:
    """Read canonical health receipts without persisting anything."""

    try:
        payload = health.calculate()
    except Exception as exc:
        return {
            "status": "UNAVAILABLE",
            "reason": "canonical_health_read_failed",
            "error_class": type(exc).__name__,
            "payload": None,
        }

    if not isinstance(payload, Mapping):
        return {
            "status": "UNAVAILABLE",
            "reason": "canonical_health_payload_invalid",
            "payload": None,
        }

    return {
        "status": "AVAILABLE",
        "payload": dict(payload),
    }


def build_current_route_view(
    *,
    router: ModelRouter,
    task: str,
    messages: Sequence[Mapping[str, Any]],
    system: str | None,
    stakes: str,
    require_reasoning: bool,
    require_vision: bool,
    budget_remaining: float | None,
    remaining_queries: int | None,
) -> dict[str, Any]:
    """Observe the canonical router without executing its route."""

    try:
        route = router.route(
            task=task,
            messages=[
                dict(message)
                for message in messages
            ],
            system=system,
            stakes=stakes,
            require_reasoning=require_reasoning,
            require_vision=require_vision,
            budget_remaining=budget_remaining,
            remaining_queries=remaining_queries,
        )
    except Exception as exc:
        return {
            "status": "UNAVAILABLE",
            "reason": "canonical_router_read_failed",
            "error_class": type(exc).__name__,
            "provider": None,
            "model_id": None,
            "model": None,
            "deployment": None,
            "local": None,
            "cost": None,
            "cost_known": None,
        }

    spec = _route_model_spec(route)

    if spec is not None:
        provider = _provider(spec)
        model_id = _model_id(spec)
        model_name = (
            _model_name(spec)
            or model_id
        )
        deployment = _deployment(spec)
        local = _is_local(spec)
        cost_known = _cost_known(spec)
    else:
        provider = _text(
            _attribute(
                route,
                "provider",
                "provider_id",
                "provider_key",
            )
        )
        model_id = (
            _text(
                _attribute(
                    route,
                    "model_id",
                    "model_key",
                )
            )
            or _text(
                _attribute(
                    route,
                    "model",
                )
            )
        )
        model_name = model_id
        deployment = None
        local = _bool(
            _attribute(
                route,
                "local",
                "is_local",
            )
        )
        cost_known = None

    raw_cost = _float(
        _attribute(
            route,
            "estimated_cost",
            "cost",
        )
    )

    # Unknown cost must remain unknown. A numeric route estimate
    # is not promoted to verified cost when the canonical model
    # registry says pricing has not been calibrated.
    cost = (
        raw_cost
        if cost_known is True
        else None
    )

    return {
        "status": "AVAILABLE",
        "provider": provider,
        "model_id": model_id,
        "model": model_name,
        "deployment": deployment,
        "local": local,
        "reason": _text(
            _attribute(
                route,
                "reason",
                "rationale",
                "explanation",
            )
        ),
        "cost": cost,
        "cost_known": cost_known,
    }


def _recommended_route_capability(
    *,
    recommended_route: Route,
    capability_view: Mapping[str, Any],
    quality_floor: float,
) -> dict[str, Any]:
    if recommended_route in {
        Route.DETERMINISTIC,
        Route.HUMAN_GATE,
    }:
        return {
            "status": "NO_MODEL_REQUIRED",
            "candidate_count": 0,
        }

    if recommended_route is Route.PREDICTIVE:
        return {
            "status": "EXTERNAL_CANONICAL_OWNER",
            "owner": "predictive_cloud",
            "candidate_count": None,
        }

    if recommended_route is Route.OPTIMIZATION:
        return {
            "status": "EXTERNAL_CANONICAL_OWNER",
            "owner": "optimization_runtime",
            "candidate_count": None,
        }

    if capability_view.get("status") != "AVAILABLE":
        return {
            "status": "UNAVAILABLE",
            "candidate_count": None,
        }

    rows = list(
        capability_view.get("candidates")
        or []
    )

    wanted_local = recommended_route in {
        Route.LOCAL_SMALL,
        Route.LOCAL_STRONG,
    }

    matching = [
        row
        for row in rows
        if row.get("local") is wanted_local
    ]

    quality_observed = [
        row
        for row in matching
        if isinstance(
            row.get("quality"),
            (int, float),
        )
        and float(row["quality"]) >= quality_floor
    ]

    unknown_placement_count = sum(
        row.get("local") is None
        for row in rows
    )

    if matching:
        status = "CANDIDATE_OBSERVED"
    elif unknown_placement_count:
        status = "PLACEMENT_UNVERIFIED"
    else:
        status = "NO_MATCHING_CANDIDATE_OBSERVED"

    return {
        "status": status,
        "candidate_count": len(matching),
        "unknown_placement_count": (
            unknown_placement_count
        ),
        "quality_floor": quality_floor,
        "quality_meeting_candidate_count": len(
            quality_observed
        ),
        "quality_unknown_candidate_count": sum(
            row.get("quality") is None
            for row in matching
        ),
        "candidate_model_ids": [
            row["model_id"]
            for row in matching
        ],
    }


def _fingerprint(
    *,
    request: HybridRequest,
    task: str,
    message_count: int,
) -> str:
    payload = {
        "task_kind": request.task_kind.value,
        "task": task,
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
        "message_count": message_count,
    }

    return sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class HybridShadowObservation:
    schema_version: str
    observed_at: str
    mode: str
    production_authority: bool
    route_applied: bool
    execution_performed: bool
    workload_fingerprint: str
    task: str
    hybrid_decision: Mapping[str, Any]
    capability_view: Mapping[str, Any]
    health_view: Mapping[str, Any]
    current_route: Mapping[str, Any]
    recommended_capability: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def observe_hybrid_route(
    *,
    request: HybridRequest,
    messages: Sequence[Mapping[str, Any]],
    task: str | None = None,
    system: str | None = None,
    stakes: str = "normal",
    require_reasoning: bool = False,
    require_vision: bool = False,
    budget_remaining: float | None = None,
    remaining_queries: int | None = None,
    registry: ModelRegistry | None = None,
    health: ModelHealth | None = None,
    router: ModelRouter | None = None,
    telemetry_sink: TelemetrySink | None = None,
) -> HybridShadowObservation:
    """Observe Hybrid versus canonical routing without execution."""

    canonical_task = (
        str(task).strip()
        if task and str(task).strip()
        else _TASK_MAP[request.task_kind]
    )

    model_registry = registry or ModelRegistry()
    model_health = health or ModelHealth()
    model_router = router or ModelRouter(
        model_registry
    )

    hybrid = recommend_route(request)

    capability_view = build_capability_view(
        registry=model_registry,
        task=canonical_task,
    )

    health_view = build_health_view(
        health=model_health,
    )

    current_route = build_current_route_view(
        router=model_router,
        task=canonical_task,
        messages=messages,
        system=system,
        stakes=stakes,
        require_reasoning=require_reasoning,
        require_vision=require_vision,
        budget_remaining=budget_remaining,
        remaining_queries=remaining_queries,
    )

    recommended_capability = (
        _recommended_route_capability(
            recommended_route=(
                hybrid.recommended_route
            ),
            capability_view=capability_view,
            quality_floor=request.quality_floor,
        )
    )

    fingerprint = _fingerprint(
        request=request,
        task=canonical_task,
        message_count=len(messages),
    )

    observation = HybridShadowObservation(
        schema_version=SCHEMA_VERSION,
        observed_at=_now(),
        mode=MODE,
        production_authority=False,
        route_applied=False,
        execution_performed=False,
        workload_fingerprint=fingerprint,
        task=canonical_task,
        hybrid_decision=hybrid.to_dict(),
        capability_view=capability_view,
        health_view=health_view,
        current_route=current_route,
        recommended_capability=(
            recommended_capability
        ),
    )

    if telemetry_sink is not None:
        trace = new_trace_context()

        emit_event(
            telemetry_sink,
            name="hybrid_compute.shadow_route",
            trace=trace,
            attributes={
                "schema_version": SCHEMA_VERSION,
                "mode": MODE,
                "production_authority": False,
                "route_applied": False,
                "execution_performed": False,
                "task": canonical_task,
                "task_kind": (
                    request.task_kind.value
                ),
                "sensitivity": (
                    request.sensitivity.value
                ),
                "recommended_route": (
                    hybrid.recommended_route.value
                ),
                "current_provider": (
                    current_route.get("provider")
                ),
                "current_model": (
                    current_route.get("model")
                ),
                "registry_status": (
                    capability_view.get("status")
                ),
                "health_status": (
                    health_view.get("status")
                ),
                "candidate_count": (
                    capability_view.get(
                        "candidate_count"
                    )
                ),
                "workload_fingerprint": fingerprint,
            },
        )

    return observation
