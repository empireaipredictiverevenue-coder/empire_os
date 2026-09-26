"""HTTP sidecar adapter for Jev-compatible Laya System-1 decisions."""
from __future__ import annotations

from dataclasses import dataclass
import json
from time import perf_counter
from typing import Any, Mapping
import urllib.error
import urllib.request

from empire_os.laya_typed_decision import (
    LayaTypedDecisionError,
    _confidence,
    _criteria,
)
from empire_os.telemetry import (
    NullTelemetrySink,
    TelemetrySink,
    TraceContext,
    emit_event,
    new_trace_context,
    typed_decision_attributes,
)
from empire_os.typed_decision_provider import (
    TypedDecisionRequest,
    TypedDecisionResult,
)


@dataclass
class LayaHttpTypedDecisionProvider:
    base_url: str = "http://127.0.0.1:8769"
    api_key: str | None = None
    timeout_s: float = 20.0
    model_key: str = "convaiinnovations/laya:onnx"
    provider_key: str = "laya_http"
    telemetry_sink: TelemetrySink | None = None

    def evaluate(
        self,
        request: TypedDecisionRequest,
        *,
        trace: TraceContext | None = None,
    ) -> TypedDecisionResult:
        request.validate()
        if len(request.allowed_labels) > 20:
            raise LayaTypedDecisionError(
                "Laya choice requests must contain 20 labels or fewer"
            )

        question_key = request.task_key
        payload = {
            "state": dict(request.state),
            "questions": {
                question_key: {
                    "type": "choice",
                    "instructions": (
                        str(request.instructions or "").strip()
                        or f"Choose the best label for {request.task_key}."
                    ),
                    "criteria": _criteria(request),
                }
            },
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        http_request = urllib.request.Request(
            self.base_url.rstrip("/") + "/v1/systemone",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        started = perf_counter()
        try:
            with urllib.request.urlopen(
                http_request,
                timeout=self.timeout_s,
            ) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            json.JSONDecodeError,
        ) as exc:
            raise LayaTypedDecisionError(
                "Laya HTTP sidecar request failed"
            ) from exc
        latency_ms = (perf_counter() - started) * 1000

        if not isinstance(raw, Mapping):
            raise LayaTypedDecisionError("Laya HTTP response must be an object")
        answers = raw.get("answers")
        if not isinstance(answers, Mapping):
            raise LayaTypedDecisionError("Laya HTTP response missing answers")
        answer = answers.get(question_key)
        if not isinstance(answer, Mapping):
            raise LayaTypedDecisionError("Laya HTTP response missing task answer")

        label = str(answer.get("choice") or "").strip()
        if label not in request.allowed_labels:
            raise LayaTypedDecisionError(
                "Laya HTTP sidecar returned disallowed label"
            )

        result = TypedDecisionResult(
            provider_key=self.provider_key,
            model_key=self.model_key,
            task_key=request.task_key,
            decision_schema_ref=request.decision_schema_ref,
            state_ref=request.state_ref,
            label=label,
            confidence=_confidence(answer, label),
            latency_ms=round(latency_ms, 3),
            source_ref=f"laya:http:shadow:{request.state_ref}",
            shadow_only=True,
            execution_authority="none",
        )
        result.validate(request)

        active_trace = trace or new_trace_context()
        emit_event(
            self.telemetry_sink or NullTelemetrySink(),
            name="ai.typed_decision",
            trace=active_trace,
            attributes=typed_decision_attributes(
                provider_key=result.provider_key,
                model_key=result.model_key,
                task_key=result.task_key,
                label=result.label,
                confidence=result.confidence,
                latency_ms=result.latency_ms,
                shadow_only=result.shadow_only,
                risk_class=request.risk_class,
            ),
        )
        return result
