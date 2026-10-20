"""Tenant-scoped canonical transaction proof for adaptive commercial intelligence.

Only an existing ExecutionBusDataRepository can read order evidence, and only
explicit owner-supplied canonical UUID order IDs are considered. No searching
for buyers, inference from source counts, writes, dispatch or training.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from empire_os.execution_bus_data_repository import ExecutionBusDataRepository
from empire_os.outcome_feedback import validate_verified_feedback

SCHEMA = "empire.commercial.canonical_outcome_intelligence.v1"
MAX_ORDERS = 20
ADAPTIVE_SCHEMA = "empire.commercial.adaptive_intelligence_control.v1"


def _uuid(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("canonical UUID string required")
    try:
        ident = UUID(value)
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("canonical UUID string required") from exc
    if ident.version not in (4, 7) or str(ident) != value.lower():
        raise ValueError("canonical UUIDv4/v7 required")
    return str(ident)


def _control_context(value: Mapping[str, Any] | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, Mapping) or (
        value.get("schema_version") != ADAPTIVE_SCHEMA
        or value.get("status") != "COMMERCIAL_DEPENDENCY_EVIDENCE_HOLD"
        or value.get("mode") != "OBSERVE"
        or value.get("execution_authority") != "none"
        or value.get("outbound_authorized") is not False
        or value.get("agent_tasks_created") is not False
        or value.get("database_writes") is not False
        or value.get("payment_execution") is not False
    ):
        raise ValueError("trusted non-executing adaptive decision required")
    from empire_os.commercial_adaptive_intelligence_control import _digest
    s = value.get("decision_signature_data")
    digest = value.get("decision_signature")
    if not isinstance(s, Mapping) or not isinstance(digest, str) or digest != _digest(s):
        raise ValueError("adaptive owner decision signature mismatch")
    return digest


def inspect_canonical_order_outcomes(
    *,
    repository: ExecutionBusDataRepository,
    tenant_id: str,
    exact_order_ids: Sequence[str],
    repo_root: str,
    now: datetime,
    adaptive_commercial_review: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Inspect only exact orders passed by the existing authorized owner.

    No returned IDs, names, contacts, tenant keys, provider references, order
    evidence bodies or secret values. Missing evidence is UNKNOWN, not zero.
    """
    if not isinstance(repository, ExecutionBusDataRepository):
        raise ValueError("original canonical data repository required")
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("timezone-aware readback time required")
    current = now.astimezone(timezone.utc)
    if not isinstance(repo_root, str) or not repo_root:
        raise ValueError("existing owner repo_root required")
    scoped_tenant = _uuid(tenant_id)
    if (
        not isinstance(exact_order_ids, (list, tuple))
        or len(exact_order_ids) > MAX_ORDERS
    ):
        raise ValueError("bounded explicit order ID collection required")
    orders = [_uuid(order) for order in exact_order_ids]
    if len(orders) != len(set(orders)):
        raise ValueError("duplicate canonical orders forbidden")
    decision_ref = _control_context(adaptive_commercial_review)

    # Existing gateway must be an authenticated canonical EmpireDB context.
    # Its owner also enforces explicit tenant equality on every query.
    try:
        backend = repository._gateway.snapshot().as_dict().get("primary_backend")
    except (ValueError, TypeError, AttributeError, KeyError) as exc:
        raise ValueError("authenticated canonical gateway required") from exc
    if backend != "empiredb":
        raise ValueError("canonical EmpireDB owner required")

    reader = getattr(repository, "verified_outcome_feedback", None)
    reader_available = callable(reader)
    verified = won = lost = no_response = financial = 0
    revenue_sum = gross_profit_sum = 0
    incomplete_actual_cost_count = 0
    blocked = len(orders) if not reader_available else 0
    for order_id in (orders if reader_available else []):
        try:
            feedback = reader(
                order_id, tenant_id=scoped_tenant,
                repo_root=repo_root, as_of=current,
            )
            validate_verified_feedback(
                feedback, tenant_id=scoped_tenant, as_of=current,
            )
            if feedback.get("fulfilment_order_id") != order_id:
                raise ValueError("source returned another canonical order")
            outcome = feedback.get("conversion_outcome")
            if outcome not in ("won", "lost", "no_response"):
                raise ValueError("terminal canonical commercial outcome required")
            if outcome == "won":
                if (
                    feedback.get("actual_revenue") is not True
                    or type(feedback.get("actual_revenue_cents")) is not int
                    or feedback["actual_revenue_cents"] <= 0
                ):
                    raise ValueError("recognized revenue proof missing")
                won += 1
                revenue_sum += feedback["actual_revenue_cents"]
                cost, profit = feedback.get("actual_cost_cents"), feedback.get("gross_profit_cents")
                if (
                    type(cost) is int and cost >= 0 and type(profit) is int
                    and profit == feedback["actual_revenue_cents"] - cost
                ):
                    gross_profit_sum += profit
                    financial += 1
                else:
                    incomplete_actual_cost_count += 1
            else:
                if feedback.get("actual_revenue") is True or feedback.get("actual_revenue_cents") is not None:
                    raise ValueError("terminal loss cannot claim received revenue")
                lost += outcome == "lost"
                no_response += outcome == "no_response"
            verified += 1
        except (ValueError, TypeError, AttributeError, LookupError, OSError, KeyError, RuntimeError):
            # The original owner may have no allowed read for this order.
            # Do not echo the raw exception/ID to a tenant-facing summary.
            blocked += 1

    complete = blocked == 0
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": (
            "NO_EXPLICIT_ORDERS_SELECTED" if not orders else
            "CANONICAL_OWNER_READER_NOT_DEPLOYED" if not reader_available else
            "CANONICAL_ORDER_EVIDENCE_PARTIAL_HOLD" if not complete else
            "CANONICAL_VERIFIED_ORDER_OUTCOMES" if verified else
            "NO_CANONICAL_ORDER_PROOF"
        ),
        "reviewed_at": current.isoformat(),
        "original_owner": "execution_bus_data_repository",
        "explicit_tenant_scoped_selection": True,
        "global_buyer_discovery_performed": False,
        "original_gateway_is_canonical_empiredb": True,
        "original_verified_outcome_reader_available": reader_available,
        "selected_exact_order_count": len(orders),
        "independently_validated_outcome_count": verified,
        "verified_won_outcome_count": won,
        "verified_lost_outcome_count": lost,
        "verified_no_response_outcome_count": no_response,
        "missing_or_invalid_order_proof_count": blocked,
        "verified_wins_with_actual_cost_and_profit_count": financial,
        "verified_wins_missing_actual_cost_count": incomplete_actual_cost_count,
        "recognized_revenue_cents_for_complete_selected_cohort": revenue_sum if complete and orders else None,
        "realized_gross_profit_cents_for_complete_selected_cohort": (
            gross_profit_sum if complete and orders and financial == won else None
        ),
        "commercial_outcome_proof_complete_for_selection": bool(orders and complete),
        "training_evidence_review_required": True,
        "model_training_authorized": False,
        "original_decision_signature": decision_ref,
        "no_link_to_historical_sales_threads_inferred": True,
        "no_buyer_capacity_activation_inferred": True,
        "no_general_market_conversion_rate_inferred": True,
        "no_customer_identifiers_exposed": True,
        "outbound_authorized": False,
        "payments_executed": False,
        "crm_mutations": False,
        "agent_tasks_created": False,
        "database_writes": False,
        "execution_authority": "none",
    }
