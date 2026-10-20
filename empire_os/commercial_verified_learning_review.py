"""Original-order, post-decision commercial calibration readiness (shadow only).

Consumes trusted canonical verified feedback and an *existing* original
prediction. Reuses source owner's verified feedback and Quant Brier score
logic. No names, tenant IDs, order IDs or raw evidence leave this report.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from empire_os.authenticated_commercial_outcome_intelligence import _uuid
from empire_os.outcome_feedback import validate_verified_feedback
from empire_os.predictive_calibration import review_commercial_prediction

SCHEMA = "empire.commercial.verified_learning_review.v1"


def review_verified_learning_candidate(
    *,
    feedback: Mapping[str, Any],
    original_prediction: Mapping[str, Any] | None,
    tenant_id: str,
    exact_order_id: str,
    now: datetime,
) -> dict[str, Any]:
    """Review only known exact canonical tenant/order references.

    The caller must obtain *feedback* using the original canonical owner
    repository's verified_outcome_feedback and not from a submitted payload.
    This is an additional validation boundary, not a producer of authenticity.
    """
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("timezone-aware review required")
    if not isinstance(feedback, Mapping):
        raise ValueError("original verified feedback object required")
    current = now.astimezone(timezone.utc)
    tenant, order = _uuid(tenant_id), _uuid(exact_order_id)
    validate_verified_feedback(feedback, tenant_id=tenant, as_of=current)
    if feedback.get("fulfilment_order_id") != order:
        raise ValueError("exact canonical order linkage required")
    outcome = feedback.get("conversion_outcome")
    if outcome not in ("won", "lost", "no_response"):
        raise ValueError("terminal original outcome required")
    amount, cost, profit = (feedback.get(x) for x in (
        "actual_revenue_cents", "actual_cost_cents", "gross_profit_cents"
    ))
    verified_revenue = (
        outcome == "won" and feedback.get("actual_revenue") is True
        and type(amount) is int and amount > 0
    )
    if outcome == "won" and not verified_revenue:
        raise ValueError("verified win requires recognized revenue")
    cost_proven = (
        verified_revenue and type(cost) is int and cost >= 0
        and type(profit) is int and profit == amount - cost
    )
    if outcome != "won" and any(x is not None for x in (amount, cost, profit)):
        raise ValueError("loss cannot claim recognized money")
    if original_prediction is None:
        brier = residual = predicted = None
        calibration_state = "ORIGINAL_PRE_OUTCOME_PREDICTION_REQUIRED"
    else:
        if not isinstance(original_prediction, Mapping):
            raise ValueError("trusted original prediction mapping required")
        review = review_commercial_prediction(
            prediction=dict(original_prediction), feedback=dict(feedback),
            tenant_id=tenant, as_of=current,
        )
        if (
            review.get("schema_version") != "empire.commercial_prediction_calibration.v1"
            or review.get("calibration_ready") is not True
            or review.get("shadow_only") is not True
            or review.get("promoted_learning") is not False
            or review.get("model_weight_mutation") is not False
            or review.get("execution_authority") != "none"
            or review.get("actual_value") != feedback["verified_label"]
        ):
            raise ValueError("original Quant calibration contract not met")
        brier = review["brier_score"]
        residual = review["signed_error"]
        predicted = review["predicted_value"]
        calibration_state = "SHADOW_METRIC_FROM_SUPPLIED_PREDICTION_ORIGIN_REVIEW_REQUIRED"

    return {
        "schema_version": SCHEMA,
        "status": calibration_state,
        "mode": "OBSERVE",
        "original_feedback_validated": True,
        "exact_tenant_and_order_bound": True,
        "original_outcome_type": outcome,
        "verified_terminal_outcome_count": 1,
        "recognized_revenue_cents": amount if verified_revenue else None,
        "verified_actual_cost_cents": cost if cost_proven else None,
        "verified_gross_profit_cents": profit if cost_proven else None,
        "actual_cost_still_required": verified_revenue and not cost_proven,
        "original_probability": predicted,
        "realized_binary_outcome": feedback["verified_label"],
        "brier_score": brier,
        "signed_probability_error": residual,
        "calibration_metric_computed": original_prediction is not None,
        "original_prediction_independently_authenticated_by_this_review": False,
        "calibration_training_ready": False,
        "economic_feedback_reviewable": cost_proven,
        "model_training_authorized": False,
        "commercial_bid_or_price_change_authorized": False,
        "next_existing_owner": (
            "revenue_os_calibration_and_model_review" if original_prediction is not None
            else "original_predictive_decision_owner"
        ),
        "source_identifiers_or_contacts_included": False,
        "synthetic_or_forecast_economics_used": False,
        "database_writes": False,
        "payments_executed": False,
        "outbound_authorized": False,
        "agent_tasks_created": False,
        "execution_authority": "none",
    }


def original_order_reader_capability() -> dict[str, Any]:
    """Static existing-owner deployment readiness; no DB/API access.

    This signal cannot establish tenant authorization, order existence or
    customer revenue. A method added in another owner's uncommitted work
    does not count as deployed until included in this executable checkout.
    """
    from empire_os.execution_bus_data_repository import ExecutionBusDataRepository
    available = callable(getattr(
        ExecutionBusDataRepository, "verified_outcome_feedback", None
    ))
    return {
        "schema_version": "empire.commercial.original_order_reader_capability.v1",
        "mode": "OBSERVE",
        "status": (
            "ORIGINAL_ORDER_READER_METHOD_PRESENT_RELEASE_NOT_ATTESTED"
            if available else "ORIGINAL_ORDER_OWNER_READER_NOT_DEPLOYED"
        ),
        "original_reader_method_available_in_running_code": available,
        "owner_reader_release_approved_by_this_check": False,
        "authenticated_tenant_and_order_selected": False,
        "canonical_database_proof_observed": False,
        "verified_order_count": None,
        "verified_revenue_cents": None,
        "next_existing_owner": "execution_bus_data_repository",
        "outbound_authorized": False,
        "database_writes": False,
        "agent_tasks_created": False,
        "execution_authority": "none",
    }
