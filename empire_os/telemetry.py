"""Provider-neutral observability primitives for EmpireOS.

Core runtime stays usable without OpenTelemetry or Langfuse installed. These
primitives create W3C-compatible trace/span identifiers, redact sensitive
attributes, and emit append-only local events that exporters can consume later.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import secrets
from typing import Any, Mapping, Protocol


_HEX_32 = re.compile(r"^[0-9a-f]{32}$")
_HEX_16 = re.compile(r"^[0-9a-f]{16}$")
_SENSITIVE_KEY = re.compile(
    r"(?:api[_-]?key|authorization|password|passwd|secret|token|cookie|private[_-]?key)",
    re.IGNORECASE,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return _safe_attributes(value)
    if isinstance(value, (list, tuple)):
        return [_safe_value(item) for item in value]
    return str(value)


def _safe_attributes(values: Mapping[str, Any] | None) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in dict(values or {}).items():
        name = str(key)
        output[name] = (
            "[REDACTED]"
            if _SENSITIVE_KEY.search(name)
            else _safe_value(value)
        )
    return output


@dataclass(frozen=True)
class TraceContext:
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    sampled: bool = True

    def validate(self) -> None:
        if not _HEX_32.fullmatch(self.trace_id):
            raise ValueError("trace_id must be 32 lowercase hex characters")
        if self.trace_id == "0" * 32:
            raise ValueError("trace_id cannot be all zeros")
        if not _HEX_16.fullmatch(self.span_id):
            raise ValueError("span_id must be 16 lowercase hex characters")
        if self.span_id == "0" * 16:
            raise ValueError("span_id cannot be all zeros")
        if self.parent_span_id is not None:
            if not _HEX_16.fullmatch(self.parent_span_id):
                raise ValueError(
                    "parent_span_id must be 16 lowercase hex characters"
                )
            if self.parent_span_id == "0" * 16:
                raise ValueError("parent_span_id cannot be all zeros")

    def to_traceparent(self) -> str:
        self.validate()
        flags = "01" if self.sampled else "00"
        return f"00-{self.trace_id}-{self.span_id}-{flags}"

    def child(self) -> "TraceContext":
        self.validate()
        return TraceContext(
            trace_id=self.trace_id,
            span_id=secrets.token_hex(8),
            parent_span_id=self.span_id,
            sampled=self.sampled,
        )


def new_trace_context(*, sampled: bool = True) -> TraceContext:
    return TraceContext(
        trace_id=secrets.token_hex(16),
        span_id=secrets.token_hex(8),
        sampled=sampled,
    )


def parse_traceparent(value: str) -> TraceContext:
    parts = str(value or "").strip().lower().split("-")
    if len(parts) != 4 or parts[0] != "00" or parts[3] not in {"00", "01"}:
        raise ValueError("invalid W3C traceparent")
    context = TraceContext(
        trace_id=parts[1],
        span_id=parts[2],
        sampled=parts[3] == "01",
    )
    context.validate()
    return context


@dataclass(frozen=True)
class TelemetryEvent:
    name: str
    trace: TraceContext
    attributes: Mapping[str, Any]
    observed_at: str

    def as_dict(self) -> dict[str, Any]:
        self.trace.validate()
        return {
            "schema_version": "empire.telemetry.event.v1",
            "name": self.name,
            "trace": asdict(self.trace),
            "traceparent": self.trace.to_traceparent(),
            "attributes": _safe_attributes(self.attributes),
            "observed_at": self.observed_at,
        }


class TelemetrySink(Protocol):
    def emit(self, event: TelemetryEvent) -> None:
        ...


class NullTelemetrySink:
    def emit(self, event: TelemetryEvent) -> None:
        event.trace.validate()


class JsonlTelemetrySink:
    """Append-only local sink. No network access and no execution authority."""

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def emit(self, event: TelemetryEvent) -> None:
        payload = event.as_dict()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")


def emit_event(
    sink: TelemetrySink,
    *,
    name: str,
    trace: TraceContext,
    attributes: Mapping[str, Any] | None = None,
    observed_at: str | None = None,
) -> TelemetryEvent:
    clean_name = str(name or "").strip()
    if not clean_name:
        raise ValueError("telemetry event name required")
    trace.validate()
    event = TelemetryEvent(
        name=clean_name,
        trace=trace,
        attributes=_safe_attributes(attributes),
        observed_at=observed_at or _utc_now(),
    )
    sink.emit(event)
    return event


def typed_decision_attributes(
    *,
    provider_key: str,
    model_key: str,
    task_key: str,
    label: str,
    confidence: float,
    latency_ms: float,
    shadow_only: bool,
    risk_class: str,
) -> dict[str, Any]:
    return {
        "ai.operation": "typed_decision",
        "ai.provider": str(provider_key),
        "ai.model": str(model_key),
        "ai.task": str(task_key),
        "ai.decision.label": str(label),
        "ai.decision.confidence": float(confidence),
        "ai.latency_ms": float(latency_ms),
        "ai.shadow_only": bool(shadow_only),
        "empire.risk_class": str(risk_class),
        "execution_authority": "none",
    }
