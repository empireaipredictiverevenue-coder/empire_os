"""Deterministic monthly Exchange seat lifecycle / invoice review, NO authority.

USD catalog commitment, per-calendar-month periods, expiry and cancellation.
Input records are never trusted as actual bank, chain or tenant receipts; their
consistency is useful for a future authenticated EmpireDB owner adapter.
No USDT auto-debit, recurring charges, entitlement writes or MRR reporting.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from calendar import monthrange
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from typing import Any
from uuid import UUID
import re

from empire_os.phase4_exchange_mrr_products import EXCHANGE_MRR_PRODUCTS

SCHEMA = "empire.exchange.seat_renewal_lifecycle_review.v1"
PRODUCTS = {r.product_code: r for r in EXCHANGE_MRR_PRODUCTS}
HEX64 = re.compile(r"^[a-f0-9]{64}$")
MAX_CYCLES = 24
ALLOWED_STATUS = {"pending", "settled_shape", "failed", "reversed", "refunded"}
ACTIVE_CONTRACT_STATUS = {"proposed", "accepted", "cancelled", "suspended"}


def _utc(value: Any) -> datetime:
    if not isinstance(value,str):
        raise ValueError("timestamp_missing")
    try:
        dt = datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError:
        raise ValueError("timestamp_malformed") from None
    if dt.tzinfo is None:
        raise ValueError("timezone_required")
    return dt.astimezone(timezone.utc)


def _uuid(value: Any) -> bool:
    if type(value) is not str:
        return False
    try:
        return str(UUID(value)) == value
    except ValueError:
        return False


def _month_boundary(anchor: datetime, count: int) -> datetime:
    """Calendar-anchored: Jan 31 → Feb 28/29 → Mar 31, not Mar 28."""
    year = anchor.year + (anchor.month - 1 + count) // 12
    month = (anchor.month - 1 + count) % 12 + 1
    if year > 9999:
        raise ValueError("subscription_period_overflow")
    day = min(anchor.day,monthrange(year,month)[1])
    return anchor.replace(year=year,month=month,day=day)


def _hold(*blockers: str) -> dict[str,Any]:
    return {
        "schema_version": SCHEMA,
        "state": "HOLD",
        "blockers": sorted(set(blockers)),
        "periods_reviewed": 0,
        "active_customer_seats_verified": 0,
        "recognized_mrr_cents": 0,
        "actual_paid_revenue_cents": 0,
        "billing_attempts": 0,
        "renewal_invoices_created": 0,
        "recurring_bsc_autodebits": 0,
        "entitlements_activated": 0,
        "outbound_sent": 0,
        "database_writes": False,
        "execution_authority": "none",
    }


def review_exchange_seat_renewal_lifecycle(
    membership: Mapping[str,Any],
    periods: Sequence[Mapping[str,Any]],
    *,
    now: datetime | None = None,
) -> dict[str,Any]:
    if not isinstance(membership,Mapping) or not isinstance(periods,(list,tuple)):
        return _hold("missing_native_membership_or_period_rows")
    if len(periods)>MAX_CYCLES:
        return _hold("unbounded_membership_renewal_history")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("timezone_aware_now_required")
    current = current.astimezone(timezone.utc)

    blockers: list[str] = []
    if not all(_uuid(membership.get(k)) for k in ("membership_id","tenant_id","buyer_id")):
        blockers.append("buyer_tenant_membership_identity_missing")
    product_code=membership.get("product_code")
    product=PRODUCTS.get(product_code) if isinstance(product_code,str) else None
    if product is None:
        blockers.append("native_exchange_product_not_found")
    contract_state = membership.get("contract_state")
    if not isinstance(contract_state,str) or contract_state not in ACTIVE_CONTRACT_STATUS:
        blockers.append("untrusted_membership_contract_status")
    terms=membership.get("commercial_terms_sha256")
    if not isinstance(terms,str) or not HEX64.fullmatch(terms):
        blockers.append("membership_contract_terms_digest_missing")
    if membership.get("source_kind") != "native_exchange_seat_monthly":
        blockers.append("legacy_strike_pack_or_other_product_cannot_activate_seat")
    if membership.get("currency")!="USD" or (
        product is not None and membership.get("monthly_price_cents")!=product.monthly_price_cents
    ):
        blockers.append("catalog_price_or_currency_drift")
    corridor_keys=membership.get("authorized_corridor_keys")
    if (not isinstance(corridor_keys,list)
            or any(not isinstance(c,str) or not c.startswith("corridor:") or len(c)>170 for c in corridor_keys)
            or len({c for c in corridor_keys if isinstance(c,str)})!=len(corridor_keys)
            or len(corridor_keys)>25
            or (product is not None and product.corridor_limit is not None
                and len(corridor_keys)>product.corridor_limit)):
        blockers.append("unauthorised_corridor_count_or_identity")

    try:
        anchor=_utc(membership.get("billing_anchor_at"))
    except ValueError:
        return _hold(*(blockers+["monthly_billing_anchor_missing"]))
    if anchor.second or anchor.microsecond:
        blockers.append("billing_anchor_precision_not_normalized")
    if (membership.get("contract_state")=="accepted" and
            membership.get("accepted_terms_evidence") is not True):
        blockers.append("signed_or_accepted_membership_terms_unproven")
    cancellation=membership.get("cancel_effective_at")
    if cancellation is None:
        stop=None
    else:
        try:
            stop=_utc(cancellation)
            if stop<anchor:
                blockers.append("cancellation_precedes_membership_start")
        except ValueError:
            stop=None
            blockers.append("invalid_cancellation_effective_time")
    if membership.get("contract_state")=="cancelled" and stop is None:
        blockers.append("cancellation_effective_receipt_missing")
    if (membership.get("contract_state")=="suspended"
            and (not isinstance(membership.get("suspension_reason"),str)
                 or membership.get("suspension_reason") not in
                    {"dispute","nonpayment","revocation","fraud_review"})):
        blockers.append("unverified_suspension_reason")
    # Reject all cross-member, duplicate or malformed period inputs instead
    # of choosing one flattering row as 'paid' and ignoring competing rows.
    indexed:dict[int,Mapping[str,Any]]={}
    unique_invoices=set()
    unique_payment_requests=set()
    unique_receipts=set()
    for row in periods:
        if not isinstance(row,Mapping):
            blockers.append("untrusted_invoice_cycle_record")
            continue
        index=row.get("period_index")
        if type(index) is not int or not 0<=index<MAX_CYCLES or index in indexed:
            blockers.append("duplicate_or_invalid_billing_cycle_index")
            continue
        indexed[index]=row
        if (row.get("membership_id")!=membership.get("membership_id")
                or row.get("tenant_id")!=membership.get("tenant_id")
                or row.get("buyer_id")!=membership.get("buyer_id")):
            blockers.append("cross_tenant_or_member_cycle_mismatch")
        for ref_field,seen,reason in (
            ("invoice_id",unique_invoices,"reused_invoice_id"),
            ("payment_request_id",unique_payment_requests,"reused_payment_request"),
            ("payment_receipt_id",unique_receipts,"reused_settlement_receipt"),
        ):
            value=row.get(ref_field)
            if value is not None:
                if not _uuid(value) or value in seen:
                    blockers.append(reason)
                seen.add(value)
        status=row.get("payment_state")
        if not isinstance(status,str) or status not in ALLOWED_STATUS:
            blockers.append("invalid_payment_state")
        if status=="settled_shape" and not all(
            row.get(v) is not None for v in
            ("invoice_id","payment_request_id","payment_receipt_id")
        ):
            blockers.append("settled_cycle_missing_payment_receipts")
        if isinstance(status,str) and status in {"reversed","refunded"} and (
            not isinstance(row.get("reversal_receipt_ref"),str)
            or not row.get("reversal_receipt_ref","").strip()):
            blockers.append("refund_or_reversal_evidence_missing")
        if row.get("membership_price_cents") != (
            product.monthly_price_cents if product else None):
            blockers.append("invoice_price_drift")
        if row.get("terms_sha256")!=terms:
            blockers.append("invoice_terms_digest_drift")
        try:
            begin=_utc(row.get("period_start"))
            end=_utc(row.get("period_end"))
            if begin!=_month_boundary(anchor,index) or end!=_month_boundary(anchor,index+1):
                blockers.append("invoice_monthly_calendar_period_mismatch")
        except ValueError:
            blockers.append("invalid_invoice_period")
        if (row.get("payment_join_state")==
            "CROSS_TABLE_PAYMENT_RECEIPT_SHAPE_CONSISTENT_NOT_AUTHENTICATED"
            and status!="settled_shape"):
            blockers.append("inconsistent_payment_join_and_period_status")
        if (status=="settled_shape" and
            row.get("payment_join_state")!=
            "CROSS_TABLE_PAYMENT_RECEIPT_SHAPE_CONSISTENT_NOT_AUTHENTICATED"):
            blockers.append("settled_cycle_lacks_native_payment_join")
    if indexed and sorted(indexed) != list(range(max(indexed)+1)):
        blockers.append("missing_prior_monthly_invoice_history")
    if blockers:
        return _hold(*blockers)

    # This is ONLY a shape/proposal, not an authentic subscriber entitlement.
    # Do not silently extrapolate future periods when >24 months elapsed.
    if current < anchor:
        period_index=None
        state="FUTURE_MEMBERSHIP_NOT_STARTED"
    else:
        offset=(current.year-anchor.year)*12+current.month-anchor.month
        if offset<0:
            offset=0
        period_index=None
        for i in sorted({max(0,offset-1),offset,offset+1}):
            if i>=MAX_CYCLES:
                continue
            if _month_boundary(anchor,i)<=current<_month_boundary(anchor,i+1):
                period_index=i
                break
        state="PERIOD_OUTSIDE_REVIEW_HORIZON" if period_index is None else "CURRENT_PERIOD_NOT_PAID"
    current_row=indexed.get(period_index) if period_index is not None else None
    if period_index is not None:
        if membership.get("contract_state")=="suspended":
            state="SUSPENDED_NO_ACCESS"
        elif stop is not None and current>=stop:
            state="CANCELLED_NO_ACCESS"
        elif membership.get("contract_state")!="accepted":
            state="NOT_YET_ACCEPTED"
        elif current_row is None:
            state="CURRENT_MONTH_HAS_NO_PAYMENT_RECORD"
        elif current_row.get("payment_state")=="settled_shape":
            state="PAID_RECEIPT_SHAPE_REVIEW_REQUIRED"
        elif current_row.get("payment_state") in ("reversed","refunded"):
            state="REFUND_OR_REVERSAL_NO_ACCESS"
        elif current_row.get("payment_state")=="failed":
            state="FAILED_PAYMENT_NO_ACCESS"
        else:
            state="PENDING_PAYMENT_NO_ACCESS"

    # Preview next month's deterministic idempotency token; never create an
    # invoice as an action or expose buyer/tenant IDs.
    next_index=(period_index+1) if period_index is not None else 0
    next_period=( _month_boundary(anchor,next_index).isoformat()
                 if next_index<MAX_CYCLES else None )
    next_token=(sha256(
        f"exchange-seat-monthly/v1:{membership.get('membership_id')}:{next_index}:"
        f"{product_code}:{terms}".encode()).hexdigest()
        if next_index<MAX_CYCLES else None)
    return {
        "schema_version":SCHEMA,
        "state":"RENEWAL_REVIEW_NO_EXECUTION",
        "hypothetical_current_period_state":state,
        "billing_period_index":period_index,
        "periods_reviewed":len(indexed),
        "period_history_is_authentic":False,
        "monthly_catalog_price_cents":product.monthly_price_cents if product else None,
        "next_period_start_utc":next_period,
        "next_invoice_idempotency_digest_preview":next_token,
        "next_invoice_requested_or_created":False,
        "seats_with_real_entitlement_verified":0,
        "recognized_mrr_cents":0,
        "actual_paid_revenue_cents":0,
        "renewal_invoices_created":0,
        "recurring_bsc_autodebits":0,
        "entitlements_activated":0,
        "outbound_sent":0,
        "database_writes":False,
        "execution_authority":"none",
        "blockers":[
            "independently_authenticated_canonical_finance_and_tenant_receipts_required",
            "unique_invoice_and_renewal_lock_in_authoritative_empiredb_writer_required",
            "approved_subscription_lifecycle_state_write_not_authorized",
            "usdt_on_bsc_requires_independent_new_monthly_payment_event",
        ],
    }
