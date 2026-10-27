"""READ-ONLY exact fulfilled-order -> BSC payment -> revenue-event continuity.

This is a consistency reviewer, NOT a blockchain verifier, settlement-finality
attestor or the original empire_revenue_recognizer's privileged RPC. Actual
records must be supplied by the existing tenant-RLS order/payment owner.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence
from uuid import UUID
import re

from empire_os.canonical_prospect_tenant_handoff import ProspectHandoffHold

SCHEMA = "empire.canonical.delivery_to_settlement_handoff.v1"
DELIVERY_SCHEMA = "empire.canonical.accepted_order_fulfilment_handoff.v1"
USDT_BSC = "0x55d398326f99059ff775485246999027b3197955"
ORDER_KEYS = ("tenant_id", "buyer_id", "prospect_id", "entity_id", "opportunity_id")
HEX_TX = re.compile(r"0x[0-9a-f]{64}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")

def _uuid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        return False

def _time(value: Any, now: datetime) -> datetime:
    if not isinstance(value, (str, datetime)):
        raise ProspectHandoffHold("EXACT_SETTLEMENT_TIMESTAMP_REQUIRED")
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    except (ValueError, TypeError, OverflowError) as exc:
        raise ProspectHandoffHold("INVALID_SETTLEMENT_TIMESTAMP") from exc
    if t.tzinfo is None or t.utcoffset() is None or t.astimezone(timezone.utc) > now:
        raise ProspectHandoffHold("FUTURE_OR_NAIVE_SETTLEMENT_TIMESTAMP")
    return t.astimezone(timezone.utc)

def _raw_units(value: Any) -> int | None:
    """Original PostgreSQL NUMERIC comes back as Decimal, not Python int."""
    if isinstance(value, (bool, float)) or not isinstance(value, (str, int, Decimal)):
        return None
    try:
        n = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if (not n.is_finite() or n <= 0 or n != n.to_integral_value()
            or n >= Decimal(2) ** 256):
        return None
    return int(n)


def _scope(row: Mapping[str, Any], delivered: Mapping[str, Any], *, order_ref: bool = False) -> None:
    if not isinstance(row, Mapping):
        raise ProspectHandoffHold("ORIGINAL_SCOPED_RECORD_REQUIRED")
    if order_ref and row.get("fulfilment_order_id") != delivered["fulfilment_order_id"]:
        raise ProspectHandoffHold("CROSS_ORDER_SETTLEMENT_REJECTED")
    for k in ORDER_KEYS:
        if k in row and row[k] is not None and row[k] != delivered[k]:
            raise ProspectHandoffHold("CROSS_TENANT_BUYER_OR_OPPORTUNITY_SETTLEMENT_REJECTED")
    if any(row.get(k) is True for k in ("synthetic", "forecast_derived", "model_inferred")):
        raise ProspectHandoffHold("INFERRED_SETTLEMENT_EVIDENCE_REJECTED")

def review_fulfilment_payment_settlement(
    delivered: Mapping[str, Any],
    order: Mapping[str, Any],
    request: Mapping[str, Any],
    evidence: Mapping[str, Any],
    *,
    as_of: datetime,
    escrow_agreement: Mapping[str, Any] | None = None,
    revenue_event: Mapping[str, Any] | None = None,
    reversals: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ProspectHandoffHold("AWARE_FINANCIAL_REVIEW_TIME_REQUIRED")
    now = as_of.astimezone(timezone.utc)
    if (not isinstance(delivered, Mapping)
            or delivered.get("schema_version") != DELIVERY_SCHEMA
            or delivered.get("mode") != "OBSERVE"
            or delivered.get("status") not in (
                "INJECTED_DELIVERY_COHERENCE_TEST_ONLY",
                "TENANT_SCOPED_DELIVERY_COHERENCE_REVIEW_ONLY")
            or delivered.get("delivery_record_coherence_verified") is not True
            or delivered.get("execution_authority") != "NONE"
            or delivered.get("revenue_verified") is not False
            or delivered.get("settlement_verified") is not False
            or delivered.get("database_writes") is not False
            or delivered.get("outbound_authorized") is not False):
        raise ProspectHandoffHold("UNTRUSTED_DELIVERY_HANDOFF")
    if (not _uuid(delivered.get("fulfilment_order_id"))
            or any(not _uuid(delivered.get(k)) for k in ORDER_KEYS)):
        raise ProspectHandoffHold("EXACT_CANONICAL_FINANCIAL_IDENTITY_REQUIRED")
    if not isinstance(order, Mapping) or order.get("id") != delivered["fulfilment_order_id"]:
        raise ProspectHandoffHold("EXACT_FULFILMENT_ORDER_REQUIRED")
    _scope(order, delivered)
    if order.get("state") not in ("delivered", "confirmed", "invoiced", "paid", "settled", "outcome_captured"):
        raise ProspectHandoffHold("POST_DELIVERY_ORDER_STATE_REQUIRED")
    _scope(request, delivered, order_ref=True)
    if (request.get("buyer_id") != delivered["buyer_id"]
            or request.get("status") != "approved"
            or not _uuid(request.get("id"))
            or not isinstance(request.get("approved_by"), str)
            or not request["approved_by"].strip()
            or request.get("settlement_mode") not in ("direct", "escrow")):
        raise ProspectHandoffHold("ORIGINAL_APPROVED_BUYER_PAYMENT_REQUEST_REQUIRED")
    approved=_time(request.get("approved_at"),now)
    if approved < _time(delivered.get("buyer_acceptance_at"),now):
        raise ProspectHandoffHold("PAYMENT_REQUEST_PREDATES_BUYER_ACCEPTANCE")
    # Expiry may be later than the review time. It is a contractual deadline,
    # not a past transaction timestamp.
    raw_expiry=request.get("expires_at")
    if not isinstance(raw_expiry,(str,datetime)):
        raise ProspectHandoffHold("PAYMENT_REQUEST_EXPIRY_REQUIRED")
    try:
        expiry=(datetime.fromisoformat(raw_expiry.replace("Z","+00:00"))
                if isinstance(raw_expiry,str) else raw_expiry)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ProspectHandoffHold("INVALID_PAYMENT_EXPIRY") from exc
    if expiry.utcoffset() is None or expiry <= approved:
        raise ProspectHandoffHold("INVALID_PAYMENT_APPROVAL_WINDOW")
    terms=(order.get("commercial_payload") or {}).get("commercial_terms_sha256")
    if (not isinstance(terms,str) or not HEX64.fullmatch(terms)
            or request.get("commercial_terms_sha256") != terms):
        raise ProspectHandoffHold("SETTLEMENT_COMMERCIAL_TERMS_MISMATCH")
    try:
        raw=request.get("amount_usdt")
        if isinstance(raw,(bool,float)) or not isinstance(raw,(str,int,Decimal)):
            raise ValueError("non-exact amount")
        amount=Decimal(str(raw))
        price=order.get("price_cents")
        if (not amount.is_finite() or amount<=0
                or type(price) is not int or price<=0
                or amount*100!=Decimal(price)):
            raise ValueError("price mismatch")
    except (InvalidOperation,ValueError,TypeError):
        raise ProspectHandoffHold("UNMATCHED_APPROVED_PAYMENT_AMOUNT") from None
    try:
        amount_raw=amount * (10 ** 18)
        if amount_raw!=amount_raw.to_integral_value():
            raise ValueError("non-integer USDT base units")
    except (InvalidOperation,ValueError):
        raise ProspectHandoffHold("NON_EXACT_USDT_BASE_UNITS") from None
    if not isinstance(reversals,(tuple,list)) or len(reversals)>20:
        raise ProspectHandoffHold("UNBOUNDED_FINANCIAL_REVERSAL_EVIDENCE")
    for reversal in reversals:
        _scope(reversal,delivered,order_ref=True)
        # Any observed reversal/dispute/chargeback means no clean settlement
        # can be inferred. No absence-of-reversals finality claim is made.
        raise ProspectHandoffHold("RECORDED_REVERSAL_OR_DISPUTE_REVIEW_REQUIRED")
    _scope(evidence,delivered)
    source=request["settlement_mode"]
    if (not _uuid(evidence.get("id"))
            or not isinstance(evidence.get("transaction_hash"),str)
            or not HEX_TX.fullmatch(evidence["transaction_hash"])
            or type(evidence.get("confirmations")) is not int
            or evidence["confirmations"]<12):
        raise ProspectHandoffHold("EXACT_BSC_TRANSACTION_RECEIPT_REQUIRED")
    if (_raw_units(evidence.get("amount_raw"))!=int(amount_raw)
            or type(evidence.get("block_number")) is not int
            or evidence["block_number"]<=0):
        raise ProspectHandoffHold("UNMATCHED_BSC_TRANSFER_AMOUNT_OR_BLOCK")
    if source=="direct":
        if escrow_agreement is not None:
            raise ProspectHandoffHold("MIXED_DIRECT_AND_ESCROW_SETTLEMENT")
        if (evidence.get("request_id")!=request["id"]
                or evidence.get("fulfilment_order_id")!=delivered["fulfilment_order_id"]
                or evidence.get("chain_id")!=56
                or type(request.get("min_block_number")) is not int
                or request["min_block_number"]<=0
                or evidence["block_number"]<request["min_block_number"]
                or evidence.get("token_contract")!=USDT_BSC
                or evidence.get("commercial_terms_sha256")!=terms
                or evidence.get("treasury_address")!=request.get("treasury_address")):
            raise ProspectHandoffHold("INVALID_DIRECT_BSC_USDT_RECEIPT_BINDING")
        evidence_source="direct_payment"
    else:
        if not isinstance(escrow_agreement,Mapping):
            raise ProspectHandoffHold("EXACT_ESCROW_AGREEMENT_REQUIRED")
        _scope(escrow_agreement,delivered)
        if (not _uuid(escrow_agreement.get("id"))
                or escrow_agreement.get("request_id")!=request["id"]
                or escrow_agreement.get("status")!="released"
                or escrow_agreement.get("commercial_terms_sha256")!=terms
                or _raw_units(escrow_agreement.get("amount_raw"))!=int(amount_raw)
                or evidence.get("agreement_id")!=escrow_agreement["id"]
                or evidence.get("action")!="released"):
            raise ProspectHandoffHold("RELEASED_ESCROW_ORDER_BINDING_REQUIRED")
        evidence_source="escrow_release"
    verified=_time(evidence.get("verified_at"),now)
    if verified<approved:
        raise ProspectHandoffHold("PAYMENT_VERIFICATION_PREDATES_APPROVAL")
    if verified>=expiry.astimezone(timezone.utc):
        raise ProspectHandoffHold("PAYMENT_VERIFICATION_AFTER_APPROVED_EXPIRY")
    result={
        "schema_version":SCHEMA,"mode":"OBSERVE",
        "status":("INJECTED_FINANCIAL_LINEAGE_COHERENCE_ONLY"
                  if delivered["status"]=="INJECTED_DELIVERY_COHERENCE_TEST_ONLY"
                  else "TENANT_SCOPED_FINANCIAL_LINEAGE_REVIEW_ONLY"),
        **{k:delivered[k] for k in ORDER_KEYS},
        "fulfilment_order_id":delivered["fulfilment_order_id"],
        "commercial_outcome_ref":delivered["delivery_evidence_ref"],
        "payment_request_id":request["id"],
        "settlement_evidence_id":evidence["id"],
        "settlement_source_reported":evidence_source,
        "settlement_transaction_hash_reported":evidence["transaction_hash"],
        "approved_price_cents":price,
        "ledger_payment_link_consistent":True,
        "payment_receipt_independently_verified_here":False,
        "blockchain_finality_independently_verified_here":False,
        "refund_and_dispute_census_complete_here":False,
        "actual_costs_independently_verified_here":False,
        "revenue_recognition_independently_verified_here":False,
        "economic_memory_authorized":False,
        "payments_executed":False,
        "outbound_authorized":False,
        "database_writes":False,
        "execution_authority":"NONE",
        "next_original_owner":"RevenueRecognition",
        "next_original_action":"VERIFY_ORIGINAL_BSC_RECEIPT_COSTS_REVERSALS_AND_RECOGNIZER_EVENT",
    }
    if revenue_event is None:
        result["revenue_event_consistent"]=False
        result["recognized_revenue_event_ref"]=None
        result["reported_recognized_cost_cents"]=None
        result["reported_recognized_margin_cents"]=None
        return result
    _scope(revenue_event,delivered,order_ref=True)
    payload=revenue_event.get("payload")
    if (not isinstance(payload,Mapping)
            or not _uuid(revenue_event.get("id"))
            or revenue_event.get("event_type")!="revenue_recognized"
            or revenue_event.get("idempotency_key")!=
                "revenue:"+delivered["fulfilment_order_id"]+":v1"
            or revenue_event.get("buyer_id")!=delivered["buyer_id"]
            or revenue_event.get("opportunity_id")!=delivered["opportunity_id"]
            or revenue_event.get("channel")!="bsc_usdt"
            or payload.get("settlement_source")!=evidence_source
            or payload.get("payment_request_id")!=request["id"]
            or payload.get("evidence_id")!=evidence["id"]
            or payload.get("transaction_hash")!=evidence["transaction_hash"]
            or payload.get("commercial_terms_sha256")!=terms
            or payload.get("settlement_asset")!="USDT"
            or payload.get("settlement_chain")!="BSC"
            or payload.get("actual_revenue") is not True
            or payload.get("actual_cost_evidence_verified") is not True
            or any(payload.get(k) is True for k in ("synthetic","forecast_derived"))):
        raise ProspectHandoffHold("CANONICAL_REVENUE_EVENT_SETTLEMENT_MISMATCH")
    cost=payload.get("actual_cost_evidence")
    if (not isinstance(cost,Mapping)
            or cost.get("fulfilment_order_id")!=delivered["fulfilment_order_id"]
            or cost.get("actual_cost_ready") is not True):
        raise ProspectHandoffHold("ORIGINAL_ACTUAL_COST_RECEIPT_MISSING")
    total=0
    cost_times=[]
    cost_ids=set()
    for kind in ("acquisition_cost","fulfilment_cost"):
        row=cost.get(kind)
        if (not isinstance(row,Mapping) or not row.get("evidence_id")
                or row.get("source_type") not in ("provider_invoice","internal_actual")
                or type(row.get("amount_cents")) is not int or row["amount_cents"]<0):
            raise ProspectHandoffHold("ORIGINAL_ACTUAL_COST_RECEIPT_MISSING")
        if row["evidence_id"] in cost_ids:
            raise ProspectHandoffHold("DUPLICATE_ACTUAL_COST_EVIDENCE_ID")
        cost_ids.add(row["evidence_id"])
        cost_times.append(_time(row.get("observed_at"),now))
        total+=row["amount_cents"]
    if (type(revenue_event.get("amount_cents")) is not int
            or type(revenue_event.get("cost_cents")) is not int
            or type(revenue_event.get("margin_cents")) is not int
            or revenue_event["amount_cents"]!=price
            or revenue_event["cost_cents"]!=total
            or revenue_event["margin_cents"]!=price-total
            or revenue_event["margin_cents"]<=0):
        raise ProspectHandoffHold("UNRECONCILED_RECOGNIZED_REVENUE_MARGINS")
    event_time=_time(revenue_event.get("occurred_at"),now)
    if event_time < verified:
        raise ProspectHandoffHold("REVENUE_EVENT_PREDATES_PAYMENT_VERIFICATION")
    if any(t>event_time for t in cost_times):
        raise ProspectHandoffHold("ACTUAL_COST_OBSERVED_AFTER_REVENUE_EVENT")
    result["revenue_event_consistent"]=True
    result["recognized_revenue_event_ref"]="canonical:commercial_events:"+revenue_event["id"]
    # Source-reported figures only. V10 must match both against its original
    # tenant-scoped feedback before previewing economic learning.
    result["reported_recognized_cost_cents"]=total
    result["reported_recognized_margin_cents"]=revenue_event["margin_cents"]
    return result
