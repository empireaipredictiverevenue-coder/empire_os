"""Optional OTLP/Langfuse export for Empire telemetry.

Core EmpireOS does not depend on OpenTelemetry. This module loads OTel lazily,
keeps a local JSONL evidence trail, and treats remote export as best-effort.
Remote observability can never grant execution authority or block business flow.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
from typing import Any, Mapping

from empire_os.telemetry import (
    JsonlTelemetrySink,
    NullTelemetrySink,
    TelemetryEvent,
    TelemetrySink,
)


class OpenTelemetryUnavailable(RuntimeError):
    pass


def _otel_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        if all(isinstance(item, (bool, int, float, str)) for item in value):
            return list(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _otel_attributes(event: TelemetryEvent) -> dict[str, Any]:
    attrs = {
        str(key): _otel_value(value)
        for key, value in dict(event.attributes).items()
    }
    attrs.update({
        "empire.telemetry.schema_version": "empire.telemetry.event.v1",
        "empire.trace.original_span_id": event.trace.span_id,
        "empire.execution_authority": "none",
    })
    if event.trace.parent_span_id:
        attrs["empire.trace.parent_span_id"] = event.trace.parent_span_id
    return attrs


@dataclass(frozen=True)
class OtlpSettings:
    endpoint: str
    headers: Mapping[str, str] = field(repr=False)
    service_name: str = "empire-os"
    environment: str = "production"

    def validate(self) -> None:
        endpoint = str(self.endpoint or "").strip()
        if not endpoint.startswith(("http://", "https://")):
            raise ValueError("OTLP endpoint must use http or https")
        if not self.service_name.strip():
            raise ValueError("OTLP service_name required")
        if not self.environment.strip():
            raise ValueError("OTLP environment required")


class OpenTelemetryEventSink:
    """Convert Empire events to batched OTLP spans."""

    def __init__(self, settings: OtlpSettings) -> None:
        settings.validate()
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
        except ImportError as exc:
            raise OpenTelemetryUnavailable(
                "OpenTelemetry exporter is not installed; "
                "install empire-os[observability]"
            ) from exc

        resource = Resource.create({
            "service.name": settings.service_name,
            "deployment.environment.name": settings.environment,
            "empire.execution_authority": "none",
        })
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(
            endpoint=settings.endpoint,
            headers=dict(settings.headers),
        )
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)

        self.settings = settings
        self._trace_api = trace
        self._provider = provider
        self._processor = processor
        self._tracer = provider.get_tracer("empire_os.telemetry")

    def emit(self, event: TelemetryEvent) -> None:
        event.trace.validate()
        try:
            from opentelemetry.trace import (
                NonRecordingSpan,
                SpanContext,
                TraceFlags,
                set_span_in_context,
            )
        except ImportError as exc:
            raise OpenTelemetryUnavailable(
                "OpenTelemetry API is not installed"
            ) from exc

        parent_span_id = (
            event.trace.parent_span_id
            or event.trace.span_id
        )
        parent = SpanContext(
            trace_id=int(event.trace.trace_id, 16),
            span_id=int(parent_span_id, 16),
            is_remote=False,
            trace_flags=(
                TraceFlags.SAMPLED
                if event.trace.sampled
                else TraceFlags.DEFAULT
            ),
        )
        context = set_span_in_context(NonRecordingSpan(parent))
        with self._tracer.start_as_current_span(
            event.name,
            context=context,
            attributes=_otel_attributes(event),
        ):
            pass

    def force_flush(self, timeout_millis: int = 5000) -> bool:
        return bool(self._provider.force_flush(timeout_millis))

    def shutdown(self) -> None:
        self._provider.shutdown()


class ResilientTelemetrySink:
    """Always keep local evidence; remote export failure is non-blocking."""

    def __init__(
        self,
        *,
        local_sink: TelemetrySink,
        remote_sink: TelemetrySink | None = None,
    ) -> None:
        self.local_sink = local_sink
        self.remote_sink = remote_sink
        self.local_failures = 0
        self.remote_failures = 0
        self.last_local_error: str | None = None
        self.last_remote_error: str | None = None

    def emit(self, event: TelemetryEvent) -> None:
        try:
            self.local_sink.emit(event)
        except Exception as exc:
            self.local_failures += 1
            self.last_local_error = type(exc).__name__

        if self.remote_sink is None:
            return
        try:
            self.remote_sink.emit(event)
        except Exception as exc:
            self.remote_failures += 1
            self.last_remote_error = type(exc).__name__


def langfuse_otlp_settings_from_env(
    env: Mapping[str, str] | None = None,
) -> OtlpSettings | None:
    values = dict(os.environ if env is None else env)
    public_key = str(values.get("LANGFUSE_PUBLIC_KEY") or "").strip()
    secret_key = str(values.get("LANGFUSE_SECRET_KEY") or "").strip()
    if not public_key or not secret_key:
        return None

    host = str(
        values.get("LANGFUSE_BASE_URL")
        or values.get("LANGFUSE_HOST")
        or "https://cloud.langfuse.com"
    ).strip().rstrip("/")
    if not host.startswith(("http://", "https://")):
        raise ValueError("LANGFUSE host must use http or https")

    auth = base64.b64encode(
        f"{public_key}:{secret_key}".encode("utf-8")
    ).decode("ascii")
    return OtlpSettings(
        endpoint=f"{host}/api/public/otel/v1/traces",
        headers={
            "Authorization": f"Basic {auth}",
            "x-langfuse-ingestion-version": "4",
        },
        service_name=str(
            values.get("OTEL_SERVICE_NAME")
            or "empire-os"
        ).strip(),
        environment=str(
            values.get("EMPIRE_ENVIRONMENT")
            or "production"
        ).strip(),
    )


def build_resilient_telemetry_sink(
    *,
    local_path: Path | str = "runtime/telemetry/events.jsonl",
    env: Mapping[str, str] | None = None,
) -> ResilientTelemetrySink:
    local = JsonlTelemetrySink(local_path)
    settings = langfuse_otlp_settings_from_env(env)
    if settings is None:
        return ResilientTelemetrySink(local_sink=local)

    try:
        remote: TelemetrySink | None = OpenTelemetryEventSink(settings)
    except OpenTelemetryUnavailable:
        remote = None

    return ResilientTelemetrySink(
        local_sink=local,
        remote_sink=remote,
    )


def disabled_remote_telemetry_sink() -> ResilientTelemetrySink:
    return ResilientTelemetrySink(
        local_sink=NullTelemetrySink(),
        remote_sink=None,
    )
