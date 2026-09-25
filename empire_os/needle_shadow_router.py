"""Shadow-only Needle 3 router for EmpireOS.

This adapter intentionally uses Needle.complete(), never Needle.run(), so model
output can recommend a tool but cannot execute Python functions or mutate state.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from typing import Any, Mapping, Sequence

from empire_os.telemetry import (
    NullTelemetrySink,
    TelemetrySink,
    TraceContext,
    emit_event,
    new_trace_context,
)


class NeedleRouterError(RuntimeError):
    pass


@dataclass(frozen=True)
class NeedleToolSchema:
    name: str
    description: str
    parameters: Mapping[str, Any]

    def validate(self) -> None:
        if not str(self.name or "").strip():
            raise ValueError("tool name required")
        if not str(self.description or "").strip():
            raise ValueError("tool description required")
        if not isinstance(self.parameters, Mapping):
            raise ValueError("tool parameters must be a JSON-schema object")
        if self.parameters.get("type") != "object":
            raise ValueError("tool parameters must use object schema")

    def as_needle_schema(self) -> dict[str, Any]:
        self.validate()
        return {
            "name": self.name,
            "description": self.description,
            "parameters": dict(self.parameters),
        }


@dataclass(frozen=True)
class NeedleRouteRequest:
    query: str
    state_ref: str
    tools: tuple[NeedleToolSchema, ...]
    system_facts: str | None = None
    confidence_threshold: float = 0.75

    def validate(self) -> None:
        if not str(self.query or "").strip():
            raise ValueError("query required")
        if not str(self.state_ref or "").strip():
            raise ValueError("state_ref required")
        if not self.tools:
            raise ValueError("at least one tool schema required")
        names = []
        for tool in self.tools:
            tool.validate()
            names.append(tool.name)
        if len(names) != len(set(names)):
            raise ValueError("tool names must be unique")
        if not 0 <= self.confidence_threshold <= 1:
            raise ValueError("confidence_threshold must be between 0 and 1")


@dataclass(frozen=True)
class NeedleRouteResult:
    provider_key: str
    model_key: str
    state_ref: str
    tool_name: str | None
    arguments: Mapping[str, Any]
    confidence: float
    requires_escalation: bool
    shadow_only: bool = True
    execution_authority: str = "none"
    tool_executed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class NeedleShadowRouter:
    """Select one tool candidate without executing it."""

    provider_key = "needle"

    def __init__(
        self,
        *,
        agent: Any,
        model_key: str = "needle3",
        telemetry_sink: TelemetrySink | None = None,
    ) -> None:
        if agent is None or not callable(getattr(agent, "complete", None)):
            raise NeedleRouterError("Needle agent with complete() required")
        self.agent = agent
        self.model_key = model_key
        self.telemetry_sink = telemetry_sink or NullTelemetrySink()

    def route(
        self,
        request: NeedleRouteRequest,
        *,
        trace: TraceContext | None = None,
    ) -> NeedleRouteResult:
        request.validate()
        active_trace = trace or new_trace_context()

        try:
            payload = self.agent.complete(
                text=request.query,
                max_new_tokens=256,
            )
        except Exception as exc:
            raise NeedleRouterError("Needle complete failed") from exc

        if not isinstance(payload, Mapping):
            raise NeedleRouterError("Needle response must be an object")

        try:
            confidence = float(payload.get("confidence", 0.0))
        except (TypeError, ValueError) as exc:
            raise NeedleRouterError("Needle confidence invalid") from exc
        if not 0 <= confidence <= 1:
            raise NeedleRouterError("Needle confidence outside 0..1")

        calls = payload.get("function_calls")
        if calls is None:
            calls = []
        if not isinstance(calls, list):
            raise NeedleRouterError("Needle function_calls must be a list")
        if len(calls) > 1:
            raise NeedleRouterError(
                "shadow router accepts at most one tool recommendation"
            )

        allowed = {tool.name for tool in request.tools}
        tool_name: str | None = None
        arguments: Mapping[str, Any] = {}
        if calls:
            call = calls[0]
            if not isinstance(call, Mapping):
                raise NeedleRouterError("Needle function call must be an object")
            tool_name = str(call.get("name") or "").strip()
            if tool_name not in allowed:
                raise NeedleRouterError("Needle returned undeclared tool")
            raw_args = call.get("arguments") or {}
            if not isinstance(raw_args, Mapping):
                raise NeedleRouterError("Needle tool arguments must be an object")
            arguments = dict(raw_args)

        requires_escalation = (
            tool_name is None
            or confidence < request.confidence_threshold
        )
        result = NeedleRouteResult(
            provider_key=self.provider_key,
            model_key=self.model_key,
            state_ref=request.state_ref,
            tool_name=tool_name,
            arguments=arguments,
            confidence=confidence,
            requires_escalation=requires_escalation,
        )

        emit_event(
            self.telemetry_sink,
            name="ai.tool_route",
            trace=active_trace,
            attributes={
                "ai.operation": "tool_route",
                "ai.provider": self.provider_key,
                "ai.model": self.model_key,
                "ai.tool.name": tool_name,
                "ai.tool.confidence": confidence,
                "ai.shadow_only": True,
                "ai.requires_escalation": requires_escalation,
                "execution_authority": "none",
                "tool_executed": False,
                "state_ref": request.state_ref,
            },
        )
        return result


def load_needle_shadow_router(
    *,
    tools: Sequence[NeedleToolSchema],
    system_facts: str | None = None,
    tool_index_path: str | None = None,
    telemetry_sink: TelemetrySink | None = None,
) -> NeedleShadowRouter:
    """Load Needle 3 lazily with telemetry disabled by default."""
    schemas = [tool.as_needle_schema() for tool in tools]
    if not schemas:
        raise NeedleRouterError("at least one tool schema required")

    os.environ.setdefault("NEEDLE_TELEMETRY", "0")
    os.environ.setdefault("DO_NOT_TRACK", "1")

    try:
        import needle
    except ImportError as exc:
        raise NeedleRouterError(
            "Needle 3 is not installed; install optional dependency empire-os[needle]"
        ) from exc

    try:
        agent = needle.Needle(
            tools=schemas,
            system=system_facts,
            tool_index_path=tool_index_path,
            generation=3,
        )
    except Exception as exc:
        raise NeedleRouterError("Needle 3 model load failed") from exc

    return NeedleShadowRouter(
        agent=agent,
        model_key="needle3",
        telemetry_sink=telemetry_sink,
    )
