"""Observed-evidence policy for Laya reply classification.

Laya is not a general reply classifier in EmpireOS. The first live Empire
benchmark (2026-09-25) produced 4/6 raw accuracy, 6/6 safe accuracy at the
0.80 generic review threshold, and zero unsafe accepts. Its strongest observed
signals were high-confidence negative and unsubscribe decisions.

This module therefore exposes a narrower shadow-specialist review. It does not
grant execution authority and cannot control outbound, payment, revenue truth,
or contact-state mutation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from empire_os.typed_decision_provider import (
    TypedDecisionRequest,
    TypedDecisionResult,
)


@dataclass(frozen=True)
class LayaReplySpecialistPolicy:
    accepted_labels: frozenset[str] = frozenset({"negative", "unsubscribe"})
    confidence_threshold: float = 0.85
    benchmark_ref: str = "empire.laya-shadow-benchmark.2026-09-25.v1"

    def validate(self) -> None:
        if not self.accepted_labels:
            raise ValueError("accepted_labels required")
        if not 0 <= self.confidence_threshold <= 1:
            raise ValueError("confidence_threshold must be between 0 and 1")


def review_laya_reply_specialist(
    *,
    request: TypedDecisionRequest,
    result: TypedDecisionResult,
    policy: LayaReplySpecialistPolicy | None = None,
) -> dict[str, Any]:
    """Review a Laya reply result under its evidence-backed shadow lane."""
    request.validate()
    result.validate(request)
    active = policy or LayaReplySpecialistPolicy()
    active.validate()

    if request.task_key != "reply_classification":
        eligible_task = False
    else:
        eligible_task = True

    label_eligible = result.label in active.accepted_labels
    confidence_eligible = result.confidence >= active.confidence_threshold
    risk_eligible = request.risk_class in {"low", "medium"}

    accepted_for_shadow_analysis = (
        eligible_task
        and label_eligible
        and confidence_eligible
        and risk_eligible
    )

    reason = "accepted_specialist_shadow_candidate"
    if not eligible_task:
        reason = "unsupported_task"
    elif not label_eligible:
        reason = "label_outside_observed_specialist_lane"
    elif not confidence_eligible:
        reason = "below_specialist_confidence_threshold"
    elif not risk_eligible:
        reason = "risk_requires_escalation"

    return {
        "schema_version": "empire.laya-reply-specialist-review.v1",
        "benchmark_ref": active.benchmark_ref,
        "label": result.label,
        "confidence": result.confidence,
        "accepted_labels": sorted(active.accepted_labels),
        "confidence_threshold": active.confidence_threshold,
        "accepted_for_shadow_analysis": accepted_for_shadow_analysis,
        "requires_escalation": not accepted_for_shadow_analysis,
        "reason": reason,
        "controls_live_route": False,
        "execution_performed": False,
        "execution_authority": "none",
        "may_send_outbound": False,
        "may_mutate_contact_state": False,
        "may_recognize_revenue": False,
        "may_move_funds": False,
    }


def observed_laya_benchmark() -> dict[str, Any]:
    """Immutable evidence snapshot from the first resident-sidecar benchmark."""
    return {
        "benchmark_ref": "empire.laya-shadow-benchmark.2026-09-25.v1",
        "cases": 6,
        "raw_accuracy": 0.6667,
        "safe_accuracy": 1.0,
        "unsafe_accepts": 0,
        "escalation_rate": 0.6667,
        "latency_ms_p50": 670.29,
        "confidence_mean": 0.5281,
        "resident_memory_bytes_observed": 1584283648,
        "resident_memory_peak_bytes_observed": 1614569472,
        "observed_high_confidence_correct_labels": [
            "negative",
            "unsubscribe",
        ],
        "production_authority": "none",
        "status": "shadow_specialist_only",
    }
