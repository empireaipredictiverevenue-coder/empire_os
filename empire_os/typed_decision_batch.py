"""Versioned, provider-neutral multi-question decision contracts.

Choice, Score and Noul are separate primitives; no provider is activated.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Mapping

KINDS = frozenset({"choice", "score", "noul"})

def _prob(v: Any) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v) or not 0 <= v <= 1:
        raise ValueError("invalid finite probability")
    return float(v)

@dataclass(frozen=True)
class DecisionQuestionV2:
    key: str
    kind: str
    instructions: str
    criteria: Mapping[str, str] = field(default_factory=dict)
    score_min: float = 0.0
    score_max: float = 100.0
    score_levels: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.key.strip() or not self.instructions.strip():
            raise ValueError("question key and instructions required")
        if self.kind not in KINDS:
            raise ValueError("unsupported decision primitive")
        if self.kind == "choice" and not 2 <= len(self.criteria) <= 20:
            raise ValueError("choice requires 2 to 20 criteria")
        if self.kind == "noul" and set(self.criteria) != {"true", "false"}:
            raise ValueError("noul requires true and false criteria")
        if self.kind == "score":
            if self.criteria:
                raise ValueError("score must not supply choice criteria")
            if self.score_levels and (
                not 2 <= len(self.score_levels) <= 20
                or any(not isinstance(v, str) or not v.strip() for v in self.score_levels)
            ):
                raise ValueError("score levels require 2 to 20 nonempty labels")
        elif self.score_levels:
            raise ValueError("score levels are score-only")
        if any(not isinstance(k, str) or not k.strip() or not isinstance(v, str) or not v.strip() for k, v in self.criteria.items()):
            raise ValueError("nonempty criteria required")
        if not isfinite(self.score_min) or not isfinite(self.score_max) or self.score_max <= self.score_min:
            raise ValueError("invalid score range")

@dataclass(frozen=True)
class DecisionBatchRequestV2:
    schema_ref: str
    state_ref: str
    state: Mapping[str, Any]
    questions: tuple[DecisionQuestionV2, ...]
    risk_class: str = "low"

    def validate(self) -> None:
        if not self.schema_ref.strip() or not self.state_ref.strip():
            raise ValueError("decision identity required")
        if self.risk_class not in {"low", "medium", "high", "consequential"}:
            raise ValueError("unsupported risk class")
        if not isinstance(self.state, Mapping) or not 1 <= len(self.questions) <= 12:
            raise ValueError("invalid batch state or count")
        keys = [q.key for q in self.questions]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate question key")
        for q in self.questions:
            q.validate()

@dataclass(frozen=True)
class DecisionBatchResultV2:
    schema_ref: str
    state_ref: str
    provider_key: str
    model_key: str
    answers: Mapping[str, Mapping[str, Any]]
    latency_ms: float
    source_ref: str
    shadow_only: bool = True
    execution_authority: str = "none"

    def validate(self, req: DecisionBatchRequestV2) -> None:
        req.validate()
        if self.schema_ref != req.schema_ref or self.state_ref != req.state_ref:
            raise ValueError("batch identity mismatch")
        if not self.provider_key or not self.model_key or not self.source_ref:
            raise ValueError("provider provenance required")
        if not isinstance(self.latency_ms, (int, float)) or not isfinite(self.latency_ms) or self.latency_ms < 0:
            raise ValueError("invalid latency")
        if self.execution_authority != "none" or not self.shadow_only:
            raise ValueError("decision batch cannot grant execution authority")
        if set(self.answers) != {q.key for q in req.questions}:
            raise ValueError("answer keys must match requested questions")
        for q in req.questions:
            answer = self.answers[q.key]
            if not isinstance(answer, Mapping):
                raise ValueError("answer must be a mapping")
            if q.kind == "choice":
                if answer.get("choice") not in q.criteria:
                    raise ValueError("choice outside defined labels")
                _prob(answer.get("confidence"))
                distribution = answer.get("probabilities")
                if distribution is not None:
                    if not isinstance(distribution, Mapping) or set(distribution) != set(q.criteria):
                        raise ValueError("probabilities must cover defined labels")
                    if abs(sum(_prob(v) for v in distribution.values()) - 1) > 0.02:
                        raise ValueError("choice probabilities not normalized")
            elif q.kind == "score":
                value = answer.get("score")
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or not q.score_min <= value <= q.score_max:
                    raise ValueError("score outside range")
                if "confidence" in answer:
                    _prob(answer["confidence"])
                distribution = answer.get("probabilities")
                if distribution is not None:
                    if (not q.score_levels or not isinstance(distribution, Mapping)
                            or set(distribution) != {str(i) for i in range(len(q.score_levels))}):
                        raise ValueError("score probabilities must match defined levels")
                    probs = {k: _prob(v) for k, v in distribution.items()}
                    if abs(sum(probs.values()) - 1) > 0.02:
                        raise ValueError("score probabilities not normalized")
                    expected = sum(i * probs[str(i)] for i in range(len(q.score_levels)))
                    if abs(float(value) - expected) > 0.025:
                        raise ValueError("score contradicts reported probability distribution")
            else:
                _prob(answer.get("probability_true"))
