"""V11: one exact EmpireOS revenue case, source-reported progress only.

A pure, bounded reducer over V7/V8/V9/V10 reviews. No DB/chain/RPC read,
queue, timer, mail, payment, revenue recognition or model-learning authority.
The original owners MUST obtain these receipts via their approved readers;
caller-supplied objects have no independent authenticity at this boundary.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
from uuid import UUID

from empire_os.canonical_prospect_tenant_handoff import ProspectHandoffHold
from empire_os.canonical_buyer_acceptance_handoff import SCHEMA as V7_SCHEMA
from empire_os.canonical_fulfilment_handoff import SCHEMA as V8_SCHEMA
from empire_os.canonical_settlement_handoff import SCHEMA as V9_SCHEMA
from empire_os.canonical_economic_memory_handoff import SCHEMA as V10_SCHEMA

SCHEMA = "empire.canonical.revenue_case_progress.v1"
IDENTITY = ("tenant_id", "buyer_id", "prospect_id", "entity_id", "opportunity_id", "fulfilment_order_id")
COST_PREFIX = "canonical:commercial_evidence_registry:"
RECEIPTS = (
    ("buyer_acceptance", V7_SCHEMA, "SIGNED_TENANT_SCOPED_ACCEPTANCE_COHERENCE_REVIEW_ONLY"),
    ("delivery", V8_SCHEMA, "TENANT_SCOPED_DELIVERY_COHERENCE_REVIEW_ONLY"),
    ("settlement", V9_SCHEMA, "TENANT_SCOPED_FINANCIAL_LINEAGE_REVIEW_ONLY"),
    ("economic_memory", V10_SCHEMA, "ORIGINAL_SHADOW_MEMORY_COHERENCE_ONLY_NOT_FINANCIAL_FINALITY"),
)

# These are evidence needs, not jobs to enqueue, and none is marked verified.
INDEPENDENT_REQUIREMENTS = (
    ("BuyerAcquisition", "SIGNED_BUYER_TERMS_BUYBOX_CAPACITY_AND_PRICE"),
    ("SmartCRM", "OWNER_AUTHENTICATED_TENANT_RPC_AND_ORDER_BINDING"),
    ("FulfilmentOperations", "INDEPENDENT_PROVIDER_DELIVERY_AND_BUYER_CONFIRMATION"),
    ("RevenueRecognition", "INDEPENDENT_BSC_OR_ESCROW_RECEIPT_AND_CHAIN_FINALITY"),
    ("RevenueRecognition", "COMPLETE_REFUND_DISPUTE_REVERSAL_CENSUS"),
    ("RevenueRecognition", "INDEPENDENT_ACQUISITION_AND_FULFILMENT_COST_PROVENANCE"),
)


def _uuid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        return False


def _hold(reason: str) -> None:
    raise ProspectHandoffHold(reason)


def _exact_false(row: Mapping[str, Any], fields: tuple[str, ...]) -> bool:
    return all(row.get(key) is False for key in fields)


def _check_receipt(row: Any, *, name: str, schema: str, status: str,
                   tenant_id: str, order_id: str) -> Mapping[str, Any]:
    if (not isinstance(row, Mapping) or row.get("schema_version") != schema
            or row.get("status") != status or row.get("mode") != "OBSERVE"
            or row.get("execution_authority") != "NONE"
            or row.get("database_writes") is not False
            or row.get("outbound_authorized") is not False):
        _hold("INVALID_OR_UNTRUSTED_" + name.upper() + "_RECEIPT")
    if (row.get("tenant_id") != tenant_id
            or row.get("fulfilment_order_id") != order_id
            or not all(_uuid(row.get(k)) for k in IDENTITY)):
        _hold("CROSS_ORDER_OR_TENANT_" + name.upper() + "_RECEIPT")
    return row


def review_one_canonical_revenue_case(*, tenant_id: str, fulfilment_order_id: str,
                                      buyer_acceptance: Mapping[str, Any] | None = None,
                                      delivery: Mapping[str, Any] | None = None,
                                      settlement: Mapping[str, Any] | None = None,
                                      economic_memory: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Review provided original receipts for exactly ONE tenant and order.

    Receipt presence only establishes internal continuity. This never turns
    source claims into external financial truth, recognised income or training.
    """
    if not _uuid(tenant_id) or not _uuid(fulfilment_order_id):
        _hold("CANONICAL_TENANT_AND_ORDER_UUID_REQUIRED")
    observations = (buyer_acceptance, delivery, settlement, economic_memory)
    for index in range(1, len(observations)):
        if observations[index] is not None and observations[index - 1] is None:
            _hold("DEPENDENT_REVENUE_HANDOFF_WITHOUT_PARENT")

    received: dict[str, Mapping[str, Any]] = {}
    for (name, schema, status), row in zip(RECEIPTS, observations):
        if row is not None:
            received[name] = _check_receipt(row, name=name, schema=schema,
                                            status=status, tenant_id=tenant_id,
                                            order_id=fulfilment_order_id)
    if received:
        first = next(iter(received.values()))
        for row in received.values():
            if any(row[k] != first[k] for k in IDENTITY):
                _hold("CROSS_RECEIPT_ORIGINAL_COMMERCIAL_IDENTITY_MISMATCH")

    a = received.get("buyer_acceptance")
    d = received.get("delivery")
    s = received.get("settlement")
    m = received.get("economic_memory")
    if a is not None:
        if (a.get("original_persisted_terms_internal_coherence") is not True
                or not _uuid(a.get("buyer_acceptance_event_id"))
                or not _exact_false(a, (
                    "independent_buyer_capacity_verified_here",
                    "external_acceptance_source_independently_authenticated_here",
                    "realised_revenue_verified", "settlement_verified", "delivery_verified"))):
            _hold("UNTRUSTED_OR_INCOMPLETE_ACCEPTANCE_COHERENCE")
    if d is not None:
        if (d.get("buyer_acceptance_event_id") != a["buyer_acceptance_event_id"]
                or d.get("delivery_record_coherence_verified") is not True
                or not isinstance(d.get("delivery_evidence_ref"), str)
                or not d["delivery_evidence_ref"].startswith("canonical:commercial_outcomes:")
                or not _exact_false(d, (
                    "provider_delivery_independently_verified_here",
                    "buyer_confirmation_independently_verified_here",
                    "buyer_capacity_independently_verified_here",
                    "revenue_verified", "settlement_verified"))):
            _hold("UNTRUSTED_OR_CROSS_ACCEPTANCE_DELIVERY")
    has_event = False
    if s is not None:
        has_event = s.get("revenue_event_consistent") is True
        if (s.get("commercial_outcome_ref") != d["delivery_evidence_ref"]
                or s.get("ledger_payment_link_consistent") is not True
                or type(s.get("revenue_event_consistent")) is not bool
                or not _uuid(s.get("payment_request_id"))
                or not _uuid(s.get("settlement_evidence_id"))
                or not _exact_false(s, (
                    "payment_receipt_independently_verified_here",
                    "blockchain_finality_independently_verified_here",
                    "refund_and_dispute_census_complete_here",
                    "actual_costs_independently_verified_here",
                    "revenue_recognition_independently_verified_here",
                    "economic_memory_authorized", "payments_executed"))):
            _hold("UNTRUSTED_OR_CROSS_DELIVERY_SETTLEMENT")
        if has_event:
            refs = s.get("reported_actual_cost_evidence_refs")
            if (not isinstance(refs, list) or len(refs) != 2
                    or len(set(map(str, refs))) != 2
                    or any(not isinstance(ref, str)
                           or not ref.startswith(COST_PREFIX)
                           or not ref.removeprefix(COST_PREFIX).strip()
                           for ref in refs)
                    or not isinstance(s.get("recognized_revenue_event_ref"), str)
                    or not s["recognized_revenue_event_ref"].startswith("canonical:commercial_events:")
                    or type(s.get("approved_price_cents")) is not int
                    or s["approved_price_cents"] <= 0
                    or type(s.get("reported_recognized_cost_cents")) is not int
                    or s["reported_recognized_cost_cents"] < 0
                    or type(s.get("reported_recognized_margin_cents")) is not int
                    or s["reported_recognized_margin_cents"] <= 0
                    or s["approved_price_cents"] - s["reported_recognized_cost_cents"]
                        != s["reported_recognized_margin_cents"]):
                _hold("UNRECONCILED_ORIGINAL_RECOGNIZER_EVENT")
        elif (s.get("recognized_revenue_event_ref") is not None
              or s.get("reported_actual_cost_evidence_refs") is not None
              or s.get("reported_recognized_cost_cents") is not None
              or s.get("reported_recognized_margin_cents") is not None):
            _hold("UNRECOGNIZED_PAYMENT_CANNOT_CLAIM_REVENUE")
    if m is not None:
        if not has_event:
            _hold("ECONOMIC_MEMORY_REQUIRES_ORIGINAL_RECOGNIZER_EVENT")
        table = ("bsc_payment_evidence" if s.get("settlement_source_reported") == "direct_payment"
                 else "bsc_escrow_evidence" if s.get("settlement_source_reported") == "escrow_release"
                 else "")
        expected_payment_ref = "canonical:" + table + ":" + s["settlement_evidence_id"]
        if (not table
                or m.get("original_owner_feedback_consistent") is not True
                or m.get("original_feedback_ref") != s["commercial_outcome_ref"]
                or m.get("original_revenue_event_ref") != s["recognized_revenue_event_ref"]
                or m.get("original_payment_evidence_ref") != expected_payment_ref
                or m.get("original_actual_cost_evidence_refs") != s["reported_actual_cost_evidence_refs"]
                or m.get("reported_revenue_cents") != s["approved_price_cents"]
                or m.get("reported_actual_cost_cents") != s["reported_recognized_cost_cents"]
                or m.get("reported_gross_profit_cents") != s["reported_recognized_margin_cents"]
                or not _exact_false(m, (
                    "original_feedback_independent_financial_attestation",
                    "complete_reversal_census_verified_here",
                    "bsc_finality_independently_verified_here",
                    "buyer_funds_independently_verified_here",
                    "economic_memory_persisted", "model_training_authorized",
                    "eligible_for_learning", "payments_executed"))):
            _hold("UNTRUSTED_OR_UNRECONCILED_ECONOMIC_MEMORY_PREVIEW")

    sequence = (
        ("BUYER_ACCEPTANCE", bool(a), "SmartCRM / BuyerAcquisition",
         "REVIEW_ORIGINAL_SIGNED_ORDER_AND_PERSISTED_TERMS"),
        ("FULFILMENT", bool(d), "FulfilmentOperations",
         "REVIEW_EXACT_ORDER_DELIVERY_OUTCOME_AND_BUYER_RECEIPT"),
        ("SETTLEMENT_LEDGER", bool(s), "RevenueRecognition",
         "RECONCILE_ORIGINAL_BSC_PAYMENT_REQUEST_AND_EVIDENCE"),
        ("RECOGNIZER_EVENT", has_event, "RevenueRecognition",
         "REVIEW_ORIGINAL_ORDER_LINKED_RECOGNIZER_EVENT"),
        ("ECONOMIC_MEMORY_SHADOW", bool(m), "EconomicMemory",
         "REVIEW_ORIGINAL_TENANT_FEEDBACK_AND_SHADOW_PREVIEW"),
    )
    next_stage = next(((owner, action, stage) for stage, observed, owner, action in sequence
                       if not observed),
                      ("RevenueRecognition", "ATTEST_INDEPENDENT_BUYER_DELIVERY_SETTLEMENT_COSTS_AND_REVERSALS",
                       "INDEPENDENT_EVIDENCE"))
    case_id = "revenue_case:" + sha256((tenant_id + ":" + fulfilment_order_id).encode()).hexdigest()[:24]
    return {
        "schema_version": SCHEMA,
        "status": "EXACT_ORDER_SOURCE_COHERENCE_ONLY_EXTERNAL_PROOF_MISSING",
        "mode": "OBSERVE", "case_id": case_id,
        "tenant_id": tenant_id, "fulfilment_order_id": fulfilment_order_id,
        "source_handoff_stages": [
            {"stage": stage, "status": "SOURCE_REPORTED_COHERENCE_ONLY" if observed else "NOT_OBSERVED"}
            for stage, observed, _, _ in sequence
        ],
        "next_original_owner": next_stage[0], "next_original_action": next_stage[1],
        "next_missing_stage": next_stage[2],
        "independent_evidence_requirements": [
            {"original_owner": owner, "required_proof": evidence, "status": "NOT_ATTESTED_BY_THIS_REVIEW"}
            for owner, evidence in INDEPENDENT_REQUIREMENTS
        ],
        "source_reported_recognizer_event": has_event,
        "source_reported_shadow_memory": bool(m),
        "contracted_buyer_independently_verified_here": False,
        "buyer_delivery_independently_verified_here": False,
        "payment_and_chain_finality_independently_verified_here": False,
        "refund_and_dispute_census_complete_here": False,
        "actual_cost_provenance_independently_verified_here": False,
        "revenue_authorized": False, "revenue_recognized_here": False,
        "economic_memory_persisted": False, "eligible_for_learning": False,
        "model_training_authorized": False, "execution_authority": "NONE",
        "queue_mutated": False, "outbound_sent": False,
        "payments_executed": False, "database_writes": False,
    }
