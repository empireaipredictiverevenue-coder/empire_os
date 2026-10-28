"""Identity-continuous buyer acceptance review, original EmpireOS components.

Calls original pure persisted-terms stage builder. Does NOT load global SQL
tables, initiate buyer delivery, assert settlement, or grant any action.
Injected fixture lineage remains test-only.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Mapping, Sequence

from empire_os.canonical_prospect_tenant_handoff import ProspectHandoffHold
from empire_os.commercial_terms_materializer import build_persisted_terms_stage

SCHEMA = "empire.canonical.buyer_acceptance_handoff.v1"
LINEAGE_SCHEMA = "empire.crm.scoped_lineage_review.v1"
MAX_EVENTS = 16
EXACT_FIELDS = ("tenant_id", "prospect_id", "entity_id", "buyer_id", "opportunity_id")

def review_same_order_buyer_acceptance(
    lineage: Mapping[str, Any],
    order: Mapping[str, Any],
    terms_review: Mapping[str, Any],
    terms_events: Sequence[Mapping[str, Any]],
    *,
    as_of: datetime,
) -> dict[str, Any]:
    if not isinstance(as_of, datetime) or as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ProspectHandoffHold("AWARE_ACCEPTANCE_REVIEW_TIME_REQUIRED")
    if (not isinstance(lineage, Mapping)
            or lineage.get("schema_version") != LINEAGE_SCHEMA
            or lineage.get("mode") != "OBSERVE"
            or lineage.get("receipt_kind") != "order"
            or lineage.get("status") not in (
                "INJECTED_SCOPED_RPC_TEST_ONLY",
                "EXACT_TENANT_SCOPED_RECEIPT_OBSERVED_NOT_PROMOTED")
            or lineage.get("execution_authority") != "NONE"
            or lineage.get("outbound_authorized") is not False
            or lineage.get("database_writes") is not False
            or lineage.get("buyer_terms_verified") is not False
            or lineage.get("settlement_verified") is not False
            or lineage.get("recognised_revenue_verified") is not False):
        raise ProspectHandoffHold("UNTRUSTED_SCOPED_ORDER_LINEAGE")
    if not isinstance(order, Mapping) or not isinstance(terms_review, Mapping):
        raise ProspectHandoffHold("CANONICAL_ORDER_AND_TERMS_REQUIRED")
    if (not isinstance(terms_events, (tuple, list))
            or len(terms_events) > MAX_EVENTS
            or any(not isinstance(e, Mapping) for e in terms_events)):
        raise ProspectHandoffHold("BOUNDED_TERMS_EVENTS_REQUIRED")

    if (not lineage.get("receipt_id")
            or str(order.get("id")) != str(lineage["receipt_id"])
            or any(not lineage.get(key) or str(order.get(key)) != str(lineage[key])
                   for key in EXACT_FIELDS)):
        raise ProspectHandoffHold("EXACT_ORDER_IDENTITY_CONTINUITY_REQUIRED")
    if (str(terms_review.get("fulfilment_order_id")) != str(order["id"])
            or terms_review.get("status") != "approved"):
        raise ProspectHandoffHold("EXACT_APPROVED_TERMS_ORDER_REQUIRED")

    context = {key: str(lineage[key]) for key in EXACT_FIELDS}
    context["fulfilment_order_id"] = str(order["id"])
    for key in ("outbound_intent_id", "closer_case_id"):
        if order.get(key) is not None:
            context[key] = order[key]
    # No second acceptance implementation. The original materializer checks
    # installed review, price/currency, single approved + accepted events,
    # temporal order, evidence hash, and explicit acceptance receipt binding.
    try:
        stage = build_persisted_terms_stage(
            order, terms_review, list(terms_events),
            context=context, as_of=as_of,
        )
    except (TypeError, ValueError, KeyError, AttributeError) as exc:
        raise ProspectHandoffHold("ORIGINAL_PERSISTED_TERMS_CONTRACT_FAILED") from exc

    if stage.get("state") != "ACCEPTED" or not stage.get("accepted_at"):
        raise ProspectHandoffHold("CANONICAL_BUYER_ACCEPTANCE_NOT_RECORDED")
    accepted = [e for e in terms_events if e.get("event_type") == "accepted"]
    if len(accepted) != 1:
        raise ProspectHandoffHold("EXACT_ONE_BUYER_ACCEPTANCE_EVENT_REQUIRED")
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "status": (
            "INJECTED_ACCEPTANCE_COHERENCE_TEST_ONLY"
            if lineage["status"] == "INJECTED_SCOPED_RPC_TEST_ONLY"
            else "SIGNED_TENANT_SCOPED_ACCEPTANCE_COHERENCE_REVIEW_ONLY"
        ),
        **context,
        "scoped_order_receipt_id": lineage["receipt_id"],
        "commercial_terms_review_id": terms_review["id"],
        "buyer_acceptance_event_id": accepted[0]["id"],
        "buyer_acceptance_ref": order["commercial_payload"]["buyer_acceptance_reference"],
        "buyer_acceptance_at": stage["accepted_at"],
        "original_persisted_terms_internal_coherence": True,
        "independent_buyer_capacity_verified_here": False,
        "external_acceptance_source_independently_authenticated_here": False,
        "delivery_verified": False,
        "payment_verified": False,
        "settlement_verified": False,
        "realised_revenue_verified": False,
        "outbound_authorized": False,
        "fulfilment_authorized": False,
        "database_writes": False,
        "execution_authority": "NONE",
    }
