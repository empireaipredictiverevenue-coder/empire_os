"""Accepted buyer order -> original delivery/outcome evidence coherence.

Pure review. It reuses original commercial_terms_materializer lineage output
and original commercial_outcomes records. Cannot authenticate provider
delivery or confer buyer confirmation, payment, revenue or model learning.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from uuid import UUID

from empire_os.canonical_prospect_tenant_handoff import ProspectHandoffHold
from empire_os.conversation_qualification import _observed_stage_row, _stage_time

SCHEMA = "empire.canonical.accepted_order_fulfilment_handoff.v1"
ACCEPTANCE_SCHEMA = "empire.canonical.buyer_acceptance_handoff.v1"
STATES = frozenset({"delivered", "confirmed", "invoiced", "paid", "settled", "outcome_captured"})
DELIVERY_KINDS = frozenset({"delivery_receipt", "buyer_feedback", "provider_event"})
IDENTITY = ("tenant_id", "buyer_id", "prospect_id", "entity_id", "opportunity_id")
MAX_OUTCOMES = 16

def _canonical_uuid(v: Any) -> bool:
    if not isinstance(v, str):
        return False
    try:
        parsed = UUID(v)
    except (TypeError, ValueError, AttributeError):
        return False
    return str(parsed) == v

def _time(value: Any, as_of: datetime) -> datetime:
    try:
        observed = _stage_time(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ProspectHandoffHold("INVALID_DELIVERY_TIMESTAMP") from exc
    if observed > as_of:
        raise ProspectHandoffHold("FUTURE_DELIVERY_EVIDENCE_HOLD")
    return observed.astimezone(timezone.utc)

def review_accepted_order_delivery(
    accepted: Mapping[str, Any],
    order: Mapping[str, Any],
    outcomes: Sequence[Mapping[str, Any]],
    *, as_of: datetime,
) -> dict[str, Any]:
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ProspectHandoffHold("AWARE_FULFILMENT_REVIEW_CLOCK_REQUIRED")
    now = as_of.astimezone(timezone.utc)
    if (not isinstance(accepted, Mapping)
            or accepted.get("schema_version") != ACCEPTANCE_SCHEMA
            or accepted.get("mode") != "OBSERVE"
            or accepted.get("original_persisted_terms_internal_coherence") is not True
            or accepted.get("status") not in (
                "INJECTED_ACCEPTANCE_COHERENCE_TEST_ONLY",
                "SIGNED_TENANT_SCOPED_ACCEPTANCE_COHERENCE_REVIEW_ONLY")
            or accepted.get("execution_authority") != "NONE"
            or accepted.get("outbound_authorized") is not False
            or accepted.get("fulfilment_authorized") is not False
            or accepted.get("database_writes") is not False
            or accepted.get("delivery_verified") is not False
            or accepted.get("settlement_verified") is not False
            or accepted.get("payment_verified") is not False):
        raise ProspectHandoffHold("UNTRUSTED_BUYER_ACCEPTANCE_HANDOFF")
    if not isinstance(order, Mapping):
        raise ProspectHandoffHold("EXACT_CANONICAL_ORDER_REQUIRED")
    if (not isinstance(outcomes, (tuple, list))
            or not 1 <= len(outcomes) <= MAX_OUTCOMES
            or any(not isinstance(x, Mapping) for x in outcomes)):
        raise ProspectHandoffHold("BOUNDED_EXACT_DELIVERY_OUTCOMES_REQUIRED")

    order_id=accepted.get("fulfilment_order_id")
    if (not _canonical_uuid(order_id)
            or accepted.get("scoped_order_receipt_id") != order_id
            or str(order.get("id")) != order_id
            or any(not _canonical_uuid(accepted.get(key))
                   or str(order.get(key)) != accepted[key]
                   for key in IDENTITY)):
        raise ProspectHandoffHold("ACCEPTANCE_AND_FULFILMENT_IDENTITY_MISMATCH")
    if order.get("state") not in STATES:
        raise ProspectHandoffHold("ORDER_NOT_DELIVERED")
    try:
        _observed_stage_row(order, as_of=now)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ProspectHandoffHold("UNTRUSTED_ORDER_STATE") from exc

    if not _canonical_uuid(accepted.get("buyer_acceptance_event_id")):
        raise ProspectHandoffHold("EXACT_ORIGINAL_ACCEPTANCE_EVENT_REQUIRED")
    accepted_at = _time(accepted.get("buyer_acceptance_at"), now)
    delivered = _time(order.get("delivered_at"), now)
    if delivered < accepted_at:
        raise ProspectHandoffHold("DELIVERY_PRECEDES_BUYER_ACCEPTANCE")
    confirmed = None
    if order.get("confirmed_at") is not None:
        confirmed = _time(order["confirmed_at"], now)
        if confirmed < delivered:
            raise ProspectHandoffHold("CONFIRMATION_PRECEDES_DELIVERY")

    exact = []
    for row in outcomes:
        if row.get("fulfilment_order_id") != order_id:
            raise ProspectHandoffHold("MIXED_OUTCOME_ORDER_IDENTITIES")
        if any(key in row and row[key] != accepted[key]
               for key in IDENTITY):
            raise ProspectHandoffHold("MIXED_OUTCOME_TENANT_OR_BUYER_IDENTITY")
        try:
            _observed_stage_row(row, as_of=now)
        except (TypeError, ValueError, AttributeError) as exc:
            raise ProspectHandoffHold("UNTRUSTED_DELIVERY_OUTCOME") from exc
        if not _canonical_uuid(row.get("id")):
            raise ProspectHandoffHold("EXACT_CANONICAL_OUTCOME_UUID_REQUIRED")
        exact.append(row)
    if len({row["id"] for row in exact}) != len(exact):
        raise ProspectHandoffHold("DUPLICATE_CANONICAL_OUTCOME")
    # Review the latest observed outcome: cannot silently ignore a subsequent
    # 'failed', 'refunded', or 'rejected' receipt to reuse a previous success.
    ordered = sorted(exact, key=lambda r: _time(r.get("recorded_at"), now))
    if (len(ordered) > 1 and _time(ordered[-1].get("recorded_at"), now)
            == _time(ordered[-2].get("recorded_at"), now)):
        raise ProspectHandoffHold("AMBIGUOUS_LATEST_DELIVERY_OUTCOME_CLOCK")
    latest=ordered[-1]
    if (latest.get("delivery_outcome") not in ("delivered", "confirmed")
            or latest.get("evidence_kind") not in DELIVERY_KINDS
            or not isinstance(latest.get("evidence_reference"), str)
            or not 1 <= len(latest["evidence_reference"].strip()) <= 400
            or not isinstance(latest.get("actor"), str)
            or not 1 <= len(latest["actor"].strip()) <= 200
            or not isinstance(latest.get("idempotency_key"), str)
            or not 8 <= len(latest["idempotency_key"].strip()) <= 160):
        raise ProspectHandoffHold("ACTUAL_DELIVERY_EVIDENCE_NOT_ESTABLISHED")
    recorded=_time(latest.get("recorded_at"),now)
    if recorded < delivered:
        raise ProspectHandoffHold("OUTCOME_PREDATES_DELIVERY")
    if latest["delivery_outcome"] == "confirmed":
        if confirmed is None or confirmed > recorded:
            raise ProspectHandoffHold("CANONICAL_BUYER_CONFIRMATION_TIME_REQUIRED")
    evidence=latest.get("evidence")
    if not isinstance(evidence, Mapping):
        raise ProspectHandoffHold("CANONICAL_DELIVERY_EVIDENCE_OBJECT_REQUIRED")
    if any(evidence.get(k) is True for k in ("synthetic", "forecast_derived", "model_inferred")):
        raise ProspectHandoffHold("SYNTHETIC_DELIVERY_EVIDENCE_REJECTED")
    if ("fulfilment_order_id" in evidence and evidence["fulfilment_order_id"] != order_id
            or "buyer_id" in evidence and evidence["buyer_id"] != accepted["buyer_id"]):
        raise ProspectHandoffHold("DELIVERY_EVIDENCE_IDENTITY_CONFLICT")
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "status": ("INJECTED_DELIVERY_COHERENCE_TEST_ONLY"
                   if accepted["status"] == "INJECTED_ACCEPTANCE_COHERENCE_TEST_ONLY"
                   else "TENANT_SCOPED_DELIVERY_COHERENCE_REVIEW_ONLY"),
        **{key: accepted[key] for key in IDENTITY},
        "fulfilment_order_id": order_id,
        "buyer_acceptance_event_id": accepted.get("buyer_acceptance_event_id"),
        "delivery_outcome_id": latest["id"],
        "delivery_evidence_ref": "canonical:commercial_outcomes:" + latest["id"],
        "reported_delivery_state": latest["delivery_outcome"],
        "delivered_at": delivered.isoformat(),
        "buyer_confirmation_recorded_at": confirmed.isoformat() if confirmed else None,
        "delivery_record_coherence_verified": True,
        "provider_delivery_independently_verified_here": False,
        "buyer_confirmation_independently_verified_here": False,
        "buyer_capacity_independently_verified_here": False,
        "settlement_verified": False,
        "revenue_verified": False,
        "economic_memory_authorized": False,
        "outbound_authorized": False,
        "fulfilment_authorized": False,
        "database_writes": False,
        "execution_authority": "NONE",
        "next_original_owner": "FulfilmentOperations",
        "next_original_action": (
            "VERIFY_INDEPENDENT_BUYER_CONFIRMATION_AND_DELIVERY_PROVIDER"
            if latest["delivery_outcome"] == "confirmed"
            else "VERIFY_INDEPENDENT_DELIVERY_PROVIDER_AND_BUYER_RECEIPT"
        ),
    }
