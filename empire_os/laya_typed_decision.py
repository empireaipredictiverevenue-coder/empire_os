"""Laya adapter for Empire's provider-neutral typed decision contract.

Laya remains shadow-only here. This adapter never grants execution authority and
never mutates production state. It converts one Empire typed-choice request into
Laya's System-1 question format and validates the result against the original
allowed label set.
"""
from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Mapping

from empire_os.typed_decision_provider import (
    TypedDecisionRequest,
    TypedDecisionResult,
)
from empire_os.telemetry import (
    NullTelemetrySink,
    TelemetrySink,
    TraceContext,
    emit_event,
    new_trace_context,
    typed_decision_attributes,
)


class LayaTypedDecisionError(RuntimeError):
    pass


def _text(value: Any) -> str:
    return str(value or "").strip()


def _criteria(request: TypedDecisionRequest) -> dict[str, str]:
    if request.label_criteria is not None:
        return {
            str(label): _text(request.label_criteria[label]) or str(label)
            for label in request.allowed_labels
        }
    return {
        str(label): str(label).replace("_", " ")
        for label in request.allowed_labels
    }


def _confidence(answer: Mapping[str, Any], label: str) -> float:
    raw = answer.get("confidence")
    if raw not in (None, ""):
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise LayaTypedDecisionError("invalid Laya confidence") from exc
        if 0 <= value <= 1:
            return value
        raise LayaTypedDecisionError("Laya confidence outside 0..1")

    for key in ("probabilities", "probs", "distribution"):
        values = answer.get(key)
        if isinstance(values, Mapping) and label in values:
            try:
                value = float(values[label])
            except (TypeError, ValueError) as exc:
                raise LayaTypedDecisionError("invalid Laya probability") from exc
            if 0 <= value <= 1:
                return value
            raise LayaTypedDecisionError("Laya probability outside 0..1")

    raise LayaTypedDecisionError("Laya result missing confidence/probability")


@dataclass
class LayaTypedDecisionProvider:
    """Adapter around an already-loaded Laya agent/router."""

    agent: Any
    model_key: str = "convaiinnovations/laya"
    provider_key: str = "laya"
    source_ref_prefix: str = "laya:shadow"
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
        if self.agent is None or not callable(getattr(self.agent, "predict", None)):
            raise LayaTypedDecisionError("loaded Laya agent with predict() required")

        question_key = request.task_key
        questions = {
            question_key: {
                "type": "choice",
                "instructions": (
                    _text(request.instructions)
                    or f"Choose the best label for {request.task_key}."
                ),
                "criteria": _criteria(request),
            }
        }

        started = perf_counter()
        try:
            payload = self.agent.predict(dict(request.state), questions)
        except Exception as exc:
            raise LayaTypedDecisionError("Laya predict failed") from exc
        latency_ms = (perf_counter() - started) * 1000

        if not isinstance(payload, Mapping):
            raise LayaTypedDecisionError("Laya response must be an object")
        answers = payload.get("answers")
        if not isinstance(answers, Mapping):
            raise LayaTypedDecisionError("Laya response missing answers")
        answer = answers.get(question_key)
        if not isinstance(answer, Mapping):
            raise LayaTypedDecisionError("Laya response missing task answer")

        label = _text(answer.get("choice"))
        if label not in request.allowed_labels:
            raise LayaTypedDecisionError("Laya returned disallowed label")

        result = TypedDecisionResult(
            provider_key=self.provider_key,
            model_key=self.model_key,
            task_key=request.task_key,
            decision_schema_ref=request.decision_schema_ref,
            state_ref=request.state_ref,
            label=label,
            confidence=_confidence(answer, label),
            latency_ms=round(latency_ms, 3),
            source_ref=f"{self.source_ref_prefix}:{request.state_ref}",
            shadow_only=True,
            execution_authority="none",
        )
        result.validate(request)
        active_trace = trace or new_trace_context()
        sink = self.telemetry_sink or NullTelemetrySink()
        emit_event(
            sink,
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


def load_laya_provider(
    *,
    model_key: str = "convaiinnovations/laya",
    subfolder: str | None = None,
    **load_kwargs: Any,
) -> LayaTypedDecisionProvider:
    """Load Laya lazily so Empire's base install does not depend on it."""
    try:
        import laya
    except ImportError as exc:
        raise LayaTypedDecisionError(
            "Laya is not installed; install the optional System-1 runtime first"
        ) from exc

    try:
        if subfolder:
            agent = laya.load(model_key, subfolder=subfolder, **load_kwargs)
            resolved_model = f"{model_key}:{subfolder}"
        else:
            agent = laya.load(model_key, **load_kwargs)
            resolved_model = model_key
    except Exception as exc:
        raise LayaTypedDecisionError("Laya model load failed") from exc

    return LayaTypedDecisionProvider(
        agent=agent,
        model_key=resolved_model,
    )
