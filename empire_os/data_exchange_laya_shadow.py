"""Governed Laya System-1 shadow review for Empire Construction Signals.

Consumes ONLY an allowlisted projection of the existing AGI evidence packet.
Uses Empire's existing Laya HTTP typed-decision provider; no new runtime,
agent timer, model weights, outbound authority or customer delivery.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping, Protocol

from empire_os.data_exchange_local_reasoning import validated_context
from empire_os.laya_http_provider import LayaHttpTypedDecisionProvider
from empire_os.laya_typed_decision import LayaTypedDecisionError
from empire_os.typed_decision_provider import (
    TypedDecisionRequest,
    TypedDecisionResult,
    review_typed_decision_result,
)

SCHEMA = "empire.data_exchange.laya_shadow_review.v1"
TASK = "construction_research_workstream"
THRESHOLD = 0.80
# Research choices only; each is an already-approved, non-executing review step.
CRITERIA = {
    "review_dataset_rights": "Review OGL provenance and third-party or personal-data restrictions first.",
    "capture_later_observations": "Capture comparable future source observations; no genuine changes have been seen.",
    "independently_verify_source_transitions": "Investigate actual changed official record fields, without inferring buyer intent.",
    "collect_independent_procurement_context": "Seek separate official procurement evidence, without inferring identity.",
    "verify_cross_source_project_identity": "Check a direct official common project reference before making any join.",
    "validate_commercial_outcomes": "Review verified and time-ordered commercial outcomes; never fabricate results.",
    "test_independent_holdout": "Test an independently anchored historical forecast holdout against a baseline.",
    "research_first_paid_buyer": "Prepare email-first, founder-review-only buyer research. Never send messages.",
}


class LayaCandidateProvider(Protocol):
    def evaluate(self, request: TypedDecisionRequest) -> TypedDecisionResult: ...


def evaluate_laya_shadow(
    packet: Mapping[str, Any],
    *,
    provider: LayaCandidateProvider | None = None,
    allow_inference: bool = False,
) -> dict[str, Any]:
    """One explicitly opted-in local choice; never grants a tool capability."""
    context = validated_context(packet)
    result: dict[str, Any] = {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "provider": "existing_laya_http",
        "model_inference_performed": False,
        "decision_status": "NOT_RUN",
        "candidate_action": None,
        "confidence": None,
        "latency_ms": None,
        "deterministic_priority": context.deterministic_priority,
        "candidate_agrees_with_base_priority": None,
        "model_does_not_override_base_plan": True,
        "source_causation_established": False,
        "independent_evidence_verified": False,
        "buyer_intent_verified": False,
        "predictive_claim_ready": False,
        "customer_delivery_enabled": False,
        "outbound_enabled": False,
        "payment_execution": False,
        "production_writes": False,
        "execution_authority": "NONE",
    }
    if not allow_inference:
        return result

    # Never transmit free-text from government records, buyers, CRM or
    # user-provided source pages. Deterministic codes and counts only.
    state = {
        "source_change_count": context.source_change_count,
        "procurement_context_count": context.procurement_context_count,
        "evidence_gap_codes": list(context.gaps),
        "baseline_priority": context.deterministic_priority,
    }
    fingerprint = sha256(json.dumps(
        state, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    request = TypedDecisionRequest(
        task_key=TASK,
        decision_schema_ref=SCHEMA,
        state_ref="empire:data_exchange:shadow:" + fingerprint,
        state=state,
        allowed_labels=context.actions,
        risk_class="low",
        instructions=(
            "Select a next INTERNAL research review for the available evidence. "
            "Rights and evidence verification have precedence. This is NOT "
            "permission to send, distribute, bill, execute or assert buyer intent."
        ),
        label_criteria={k: CRITERIA[k] for k in context.actions},
    )
    client = provider if provider is not None else LayaHttpTypedDecisionProvider(
        timeout_s=6.0,
    )
    try:
        candidate = client.evaluate(request)
        audited = review_typed_decision_result(
            request=request, result=candidate,
            confidence_threshold=THRESHOLD,
        )
    except (LayaTypedDecisionError, ValueError, TypeError, KeyError,
            OSError, TimeoutError, RuntimeError):
        return {
            **result,
            "decision_status": "HOLD_PROVIDER_OR_VALIDATION_FAILURE",
        }
    if (
        candidate.shadow_only is not True
        or candidate.execution_authority != "none"
        or not candidate.provider_key.startswith("laya")
        or candidate.label not in context.actions
        or audited["controls_live_route"] is not False
        or audited["execution_performed"] is not False
    ):
        return {**result, "decision_status": "REJECTED_AUTHORITY_OR_PROVIDER"}
    if audited["requires_escalation"]:
        return {
            **result,
            "model_inference_performed": True,
            "decision_status": "HOLD_LOW_CONFIDENCE",
            "confidence": round(candidate.confidence, 4),
            "latency_ms": candidate.latency_ms,
        }
    return {
        **result,
        "model_inference_performed": True,
        "decision_status": "ADVISORY_LABEL_SCHEMA_VERIFIED",
        "candidate_action": candidate.label,
        "confidence": round(candidate.confidence, 4),
        "latency_ms": candidate.latency_ms,
        "candidate_agrees_with_base_priority": (
            candidate.label == context.deterministic_priority
        ),
    }
