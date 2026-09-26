"""Provider-neutral typed decision capability contract.

No provider implementation is activated here. This contract lets Empire plug in
Jev, a local classifier, a structured-output LLM, or deterministic rules behind
one audited interface.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Protocol


@dataclass(frozen=True)
class TypedDecisionRequest:
    task_key: str
    decision_schema_ref: str
    state_ref: str
    state: Mapping[str, Any]
    allowed_labels: tuple[str, ...]
    risk_class: str = "low"
    instructions: str | None = None
    label_criteria: Mapping[str, str] | None = None

    def validate(self) -> None:
        if not self.task_key.strip():
            raise ValueError("task_key required")
        if not self.decision_schema_ref.strip():
            raise ValueError("decision_schema_ref required")
        if not self.state_ref.strip():
            raise ValueError("state_ref required")
        if not self.allowed_labels:
            raise ValueError("allowed_labels required")
        if len(set(self.allowed_labels)) != len(self.allowed_labels):
            raise ValueError("allowed_labels must be unique")
        if self.risk_class not in {"low", "medium", "high", "consequential"}:
            raise ValueError("unsupported risk_class")
        if self.label_criteria is not None:
            criteria_keys = set(self.label_criteria)
            allowed = set(self.allowed_labels)
            if criteria_keys != allowed:
                raise ValueError("label_criteria keys must exactly match allowed_labels")


@dataclass(frozen=True)
class TypedDecisionResult:
    provider_key: str
    model_key: str
    task_key: str
    decision_schema_ref: str
    state_ref: str
    label: str
    confidence: float
    latency_ms: float
    source_ref: str
    shadow_only: bool = True
    execution_authority: str = "none"

    def validate(self, request: TypedDecisionRequest) -> None:
        request.validate()
        if self.task_key != request.task_key:
            raise ValueError("task_key mismatch")
        if self.decision_schema_ref != request.decision_schema_ref:
            raise ValueError("decision_schema_ref mismatch")
        if self.state_ref != request.state_ref:
            raise ValueError("state_ref mismatch")
        if self.label not in request.allowed_labels:
            raise ValueError("decision label not allowed by schema")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if self.latency_ms < 0:
            raise ValueError("latency_ms must be nonnegative")
        if self.execution_authority != "none":
            raise ValueError("typed decision provider cannot grant execution authority")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class TypedDecisionProvider(Protocol):
    provider_key: str

    def evaluate(self, request: TypedDecisionRequest) -> TypedDecisionResult:
        ...


class DisabledTypedDecisionProvider:
    """Fail-closed placeholder until a provider is explicitly activated."""

    provider_key = "disabled"

    def evaluate(self, request: TypedDecisionRequest) -> TypedDecisionResult:
        request.validate()
        raise RuntimeError("typed_decision_provider_not_activated")


def review_typed_decision_result(
    *,
    request: TypedDecisionRequest,
    result: TypedDecisionResult,
    confidence_threshold: float,
) -> dict[str, Any]:
    request.validate()
    result.validate(request)
    if not 0 <= confidence_threshold <= 1:
        raise ValueError("confidence_threshold must be between 0 and 1")

    requires_escalation = (
        result.confidence < confidence_threshold
        or request.risk_class in {"high", "consequential"}
    )
    return {
        "schema_version": "typed_decision_result_review.v1",
        "request": {
            "task_key": request.task_key,
            "decision_schema_ref": request.decision_schema_ref,
            "state_ref": request.state_ref,
            "allowed_labels": list(request.allowed_labels),
            "risk_class": request.risk_class,
            "instructions": request.instructions,
            "label_criteria": (
                dict(request.label_criteria)
                if request.label_criteria is not None
                else None
            ),
        },
        "result": result.as_dict(),
        "confidence_threshold": confidence_threshold,
        "requires_escalation": requires_escalation,
        "candidate_decision_accepted_for_shadow_analysis": not requires_escalation,
        "controls_live_route": False,
        "execution_performed": False,
        "execution_authority": "none",
    }
