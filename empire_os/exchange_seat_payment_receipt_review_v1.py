"""Native EmpireDB Exchange seat invoice/BSC evidence join, evidence-only.

Consumes canonical read-model *shapes* from authorized independent owner, never
fetches secrets or DB rows itself. Validates identity, monthly plan, expiry,
direct BSC USDT payment, terms and quoted FX amount cross-table. Still cannot
authenticate its supplied inputs: no entitlement/recognized revenue may be
granted or reported based on this function alone.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID
import re

from empire_os.phase4_exchange_mrr_products import EXCHANGE_MRR_PRODUCTS

SCHEMA = "empire.exchange.seat_native_payment_join_review.v1"
TOKEN = "0x55d398326f99059ff775485246999027b3197955"
HEX64 = re.compile(r"^[a-f0-9]{64}$")
HASH = re.compile(r"^0x[a-f0-9]{64}$")
ADDRESS = re.compile(r"^0x[a-f0-9]{40}$")
PRODUCTS = {p.product_code:p for p in EXCHANGE_MRR_PRODUCTS}


def _uuid(value: Any) -> str:
    try:
        if type(value) is not str:
            raise ValueError("uuid_string")
        return str(UUID(value))
    except (TypeError,ValueError,AttributeError):
        raise ValueError("untrusted_native_uuid") from None


def _timestamp(value: Any) -> datetime:
    if not isinstance(value,str):
        raise ValueError("missing_native_datetime")
    try:
        t=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError:
        raise ValueError("invalid_native_datetime") from None
    if t.tzinfo is None:
        raise ValueError("naive_native_datetime")
    return t.astimezone(timezone.utc)


def _decimal(value: Any) -> Decimal:
    if type(value) not in (str, int, Decimal):
        raise ValueError("untrusted_payment_amount")
    try:
        x=Decimal(str(value))
    except InvalidOperation:
        raise ValueError("invalid_payment_amount") from None
    if not x.is_finite() or x <= 0 or x.as_tuple().exponent < -18:
        raise ValueError("invalid_payment_precision")
    return x


def _safe_hold(reasons: list[str]) -> dict[str, Any]:
    return {
        "schema_version":SCHEMA,
        "state":"HOLD",
        "blockers":sorted(set(reasons)),
        "buyer_or_order_identifiers_emitted":False,
        "payment_hash_or_wallet_emitted":False,
        "canonical_authority_authenticated":False,
        "origin_rows_independently_authenticated":False,
        "subscription_entitlement_authorized":False,
        "seat_activated":False,
        "actual_paid_subscription_count_verified":0,
        "actual_mrr_cents_recognized":0,
        "invoice_settlement_authorized":False,
        "usage_or_overage_billed":False,
        "lead_delivery_authorized":False,
        "database_writes":False,
        "external_messages_sent":0,
        "execution_authority":"none",
    }


def review_exchange_membership_payment_join(
    *,
    order: Mapping[str, Any],
    request: Mapping[str, Any],
    evidence: Mapping[str, Any],
    finance_quote: Mapping[str, Any],
    now: datetime | None = None,
)->dict[str,Any]:
    """Cross-check one existing native order, BSC proof and monthly quote.

    Finance must independently verify source authenticity and process actual
    entitlements/recognition with governed DB writer. This never does it.
    """
    if not all(isinstance(x,Mapping) for x in (order,request,evidence,finance_quote)):
        return _safe_hold(["incomplete_native_owner_rows"])
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("timezone_aware_now_required")
    now=now.astimezone(timezone.utc)
    blockers=[]
    try:
        oid=_uuid(order.get("id"))
        buyer=_uuid(order.get("buyer_id"))
        rid=_uuid(request.get("id"))
        if _uuid(request.get("fulfilment_order_id"))!=oid or _uuid(request.get("buyer_id"))!=buyer:
            blockers.append("payment_request_order_buyer_mismatch")
        if _uuid(evidence.get("request_id"))!=rid or _uuid(evidence.get("fulfilment_order_id"))!=oid:
            blockers.append("payment_evidence_request_order_mismatch")
        if _uuid(finance_quote.get("fulfilment_order_id"))!=oid or _uuid(finance_quote.get("buyer_id"))!=buyer:
            blockers.append("finance_quote_buyer_order_mismatch")
    except ValueError:
        blockers.append("native_identity_join_missing_or_invalid")

    payload=order.get("commercial_payload")
    if not isinstance(payload,Mapping):
        return _safe_hold(blockers+["missing_native_order_commercial_payload"])
    product_code=payload.get("exchange_seat_product_code")
    product=PRODUCTS.get(product_code) if isinstance(product_code,str) else None
    if product is None:
        blockers.append("order_not_specific_exchange_seat_plan")
    if (payload.get("purchase_purpose")!="exchange_seat_monthly_membership"
            or order.get("state") not in {"accepted","invoiced","paid","settled"}):
        blockers.append("not_a_valid_monthly_membership_order")
    if (type(order.get("quantity")) is not int or order.get("quantity")!=1
            or type(order.get("price_cents")) is not int or product is None
            or order.get("price_cents") != (product.monthly_price_cents if product else None)
            or payload.get("price_currency")!="USD"):
        blockers.append("membership_product_price_or_quantity_mismatch")

    try:
        period_start=_timestamp(payload.get("membership_period_start"))
        period_end=_timestamp(payload.get("membership_period_end"))
        if not (period_start<=now<period_end):
            blockers.append("membership_period_not_current")
        delta=(period_end-period_start).days
        if delta<28 or delta>31 or (period_end-period_start).total_seconds()>32*86400:
            blockers.append("membership_period_not_monthly")
        if finance_quote.get("membership_period_start")!=payload.get("membership_period_start") or finance_quote.get("membership_period_end")!=payload.get("membership_period_end"):
            blockers.append("finance_quote_period_mismatch")
    except ValueError:
        blockers.append("unverifiable_monthly_period")
    try:
        expiry=_timestamp(request.get("expires_at"))
        approved=_timestamp(request.get("approved_at"))
        verified=_timestamp(evidence.get("verified_at"))
        # The customer may continue using the current paid membership after the
        # *payment request* expiry, as long as payment was verified in-window.
        if not approved<=verified<expiry:
            blockers.append("settlement_outside_approved_request_window")
        if verified>now:
            blockers.append("payment_verified_in_future")
    except ValueError:
        blockers.append("incomplete_approved_payment_window")
    if (request.get("status")!="approved"
            or not isinstance(request.get("approved_by"),str)
            or not request.get("approved_by","").strip()):
        blockers.append("missing_payment_operator_approval")
    terms=payload.get("commercial_terms_sha256")
    if (not isinstance(terms,str) or not HEX64.fullmatch(terms)
            or any(value!=terms for value in (
                request.get("commercial_terms_sha256"),
                evidence.get("commercial_terms_sha256"),
                finance_quote.get("commercial_terms_sha256"),
            ))):
        blockers.append("commercial_terms_hash_mismatch")
    if (request.get("settlement_mode")!="direct"
            or evidence.get("chain_id")!=56
            or evidence.get("token_contract")!=TOKEN):
        blockers.append("wrong_bsc_chain_token_or_settlement")
    if (type(evidence.get("confirmations")) is not int
            or evidence["confirmations"]<12
            or type(evidence.get("block_number")) is not int
            or type(request.get("min_block_number")) is not int
            or evidence["block_number"]<request["min_block_number"]):
        blockers.append("bsc_finality_or_block_floor_missing")
    if (not isinstance(evidence.get("transaction_hash"),str)
            or not HASH.fullmatch(evidence["transaction_hash"])):
        blockers.append("invalid_bsc_transaction_hash")
    for field in ("treasury_address",):
        addr=request.get(field)
        if (not isinstance(addr,str) or not ADDRESS.fullmatch(addr)
                or evidence.get(field)!=addr):
            blockers.append("bsc_treasury_mismatch")
    if (not isinstance(request.get("payer_address"),str)
            or not ADDRESS.fullmatch(request["payer_address"])
            or evidence.get("sender_address")!=request.get("payer_address")):
        blockers.append("bsc_payer_mismatch")

    # Product catalog is USD. USDT amount must be established by an independently
    # approved FX/quotation and raw token transfer, not coerced USD==USDT.
    try:
        requested=_decimal(request.get("amount_usdt"))
        quoted=_decimal(finance_quote.get("amount_usdt"))
        raw_amount=evidence.get("amount_raw")
        if type(raw_amount) not in (int,str,Decimal):
            raise ValueError("raw_uint256_not_integer")
        raw=Decimal(str(raw_amount))
        if raw!=raw.to_integral_value() or raw<=0:
            raise ValueError("invalid_raw_uint256")
        if requested!=quoted or raw!=requested*Decimal(10)**18:
            blockers.append("bsc_payment_amount_quote_mismatch")
        if finance_quote.get("monthly_usd_price_cents") != (
                product.monthly_price_cents if product else None):
            blockers.append("usd_plan_price_quote_mismatch")
        if finance_quote.get("quote_basis")!="finance_reviewed_usdt_conversion":
            blockers.append("finance_quote_rate_evidence_missing")
        if (not isinstance(finance_quote.get("rate_evidence_ref"),str)
                or not 8<=len(finance_quote["rate_evidence_ref"])<=160):
            blockers.append("finance_exchange_rate_receipt_not_provided")
    except (ValueError,InvalidOperation,OverflowError):
        blockers.append("invalid_bsc_quote_or_token_amount")
    if blockers:
        return _safe_hold(blockers)

    return {
        **_safe_hold(["independent_readonly_db_source_attestation_required",
                     "finance_settlement_and_entitlement_owner_review_required",
                     "canonical_idempotency_and_replay_check_required",
                     "signed_membership_terms_and_real_tenant_authority_required"]),
        "state":"CROSS_TABLE_PAYMENT_RECEIPT_SHAPE_CONSISTENT_NOT_AUTHENTICATED",
        "product_code":product_code,
        "monthly_catalog_price_cents":product.monthly_price_cents,
        "price_currency":"USD",
        "order_request_evidence_quote_matched_within_input":True,
        "bsc_min_confirmations_observed":evidence["confirmations"],
        "recurring_membership_auto_debit_verified":False,
        "usage_billing_separate":True,
        "member_identity_scope":"PSEUDONYM_ONLY_NOT_OUTPUT",
        "next_owner":"existing_canonical_empiredb_checkout_payment_and_crm_entitlement_owner",
    }
