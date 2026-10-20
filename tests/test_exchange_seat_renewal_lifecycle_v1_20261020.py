"""Synthetic monthly cycle and idempotency tests; NEVER assert revenue/seat."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import pytest

from empire_os.exchange_seat_renewal_lifecycle_v1 import (
    _month_boundary,
    review_exchange_seat_renewal_lifecycle as review,
)

BUYER = "22222222-2222-4222-8222-222222222222"
TENANT = "33333333-3333-4333-8333-333333333333"
MEMBER = "44444444-4444-4444-8444-444444444444"
INV = "55555555-5555-4555-8555-555555555555"
REQ = "66666666-6666-4666-8666-666666666666"
RCPT = "77777777-7777-4777-8777-777777777777"
TERMS = "a"*64
NOW = datetime(2026,10,20,19,10,tzinfo=timezone.utc)

def membership(**overrides):
    m={
        "membership_id":MEMBER,
        "tenant_id":TENANT,
        "buyer_id":BUYER,
        "product_code":"exchange_seat_growth",
        "source_kind":"native_exchange_seat_monthly",
        "contract_state":"accepted",
        "accepted_terms_evidence":True,
        "billing_anchor_at":"2026-10-01T00:00:00Z",
        "currency":"USD",
        "monthly_price_cents":24900,
        "commercial_terms_sha256":TERMS,
        "authorized_corridor_keys":[
            "corridor:v1:roofing:tampa:qualified_lead:lead"
        ],
        "cancel_effective_at":None,
    }
    m.update(overrides)
    return m

def paid(index=0, **overrides):
    p={
        "membership_id":MEMBER,"buyer_id":BUYER,"tenant_id":TENANT,
        "period_index":index,
        "period_start":f"2026-{10+index:02d}-01T00:00:00Z",
        "period_end":f"2026-{11+index:02d}-01T00:00:00Z",
        "invoice_id":INV,
        "payment_request_id":REQ,
        "payment_receipt_id":RCPT,
        "payment_state":"settled_shape",
        "payment_join_state":"CROSS_TABLE_PAYMENT_RECEIPT_SHAPE_CONSISTENT_NOT_AUTHENTICATED",
        "membership_price_cents":24900,
        "terms_sha256":TERMS,
    }
    p.update(overrides)
    return p

def check(m=None,rows=None,now=NOW):
    return review(m if m is not None else membership(), rows if rows is not None else [paid()], now=now)


def test_correct_synthetic_month_shape_never_creates_real_seat_or_mrr():
    result=check()
    assert result["state"]=="RENEWAL_REVIEW_NO_EXECUTION"
    assert result["hypothetical_current_period_state"]=="PAID_RECEIPT_SHAPE_REVIEW_REQUIRED"
    assert result["next_period_start_utc"]=="2026-11-01T00:00:00+00:00"
    assert result["next_invoice_requested_or_created"] is False
    assert result["entitlements_activated"]==0
    assert result["recognized_mrr_cents"]==0
    assert result["recurring_bsc_autodebits"]==0
    out=json.dumps(result)
    assert BUYER not in out and TENANT not in out and MEMBER not in out
    assert INV not in out and REQ not in out and RCPT not in out


def test_calendar_anchor_month_end_leap_year_and_stable_key():
    anchor=datetime(2024,1,31,0,0,tzinfo=timezone.utc)
    assert _month_boundary(anchor,1).isoformat()=="2024-02-29T00:00:00+00:00"
    assert _month_boundary(anchor,2).isoformat()=="2024-03-31T00:00:00+00:00"
    assert _month_boundary(anchor,13).isoformat()=="2025-02-28T00:00:00+00:00"
    a=check()
    b=check()
    assert a["next_invoice_idempotency_digest_preview"]==b["next_invoice_idempotency_digest_preview"]


@pytest.mark.parametrize("status,expected",[
    ("pending","PENDING_PAYMENT_NO_ACCESS"),
    ("failed","FAILED_PAYMENT_NO_ACCESS"),
    ("refunded","REFUND_OR_REVERSAL_NO_ACCESS"),
    ("reversed","REFUND_OR_REVERSAL_NO_ACCESS"),
])
def test_nonsettled_payment_never_hides_renewal_failure(status,expected):
    data=paid()
    data["payment_state"]=status
    data["payment_join_state"]="NOT_SETTLED"
    if status in ("refunded","reversed"):
        data["reversal_receipt_ref"]="finance-reversal-review-only"
    assert check(rows=[data])["hypothetical_current_period_state"]==expected


def test_future_expired_cancelled_suspended_scenarios():
    assert check(now=datetime(2026,9,20,tzinfo=timezone.utc))["hypothetical_current_period_state"]=="FUTURE_MEMBERSHIP_NOT_STARTED"
    assert check(rows=[],now=NOW)["hypothetical_current_period_state"]=="CURRENT_MONTH_HAS_NO_PAYMENT_RECORD"
    assert check(m=membership(contract_state="suspended",suspension_reason="dispute"))["hypothetical_current_period_state"]=="SUSPENDED_NO_ACCESS"
    assert check(m=membership(contract_state="cancelled",cancel_effective_at="2026-10-10T00:00:00Z"))["hypothetical_current_period_state"]=="CANCELLED_NO_ACCESS"
    assert check(m=membership(contract_state="proposed",accepted_terms_evidence=False))["hypothetical_current_period_state"]=="NOT_YET_ACCEPTED"


@pytest.mark.parametrize("field,value,expected",[
    ("product_code","not-a-plan","native_exchange_product_not_found"),
    ("source_kind","legacy_strike_packs","legacy_strike_pack_or_other_product_cannot_activate_seat"),
    ("monthly_price_cents",9900,"catalog_price_or_currency_drift"),
    ("currency","USDT","catalog_price_or_currency_drift"),
    ("commercial_terms_sha256","unverified","membership_contract_terms_digest_missing"),
    ("tenant_id",BUYER[:-3],"buyer_tenant_membership_identity_missing"),
    ("contract_state","paid_live","untrusted_membership_contract_status"),
    ("authorized_corridor_keys",["corridor:a"]*6,"unauthorised_corridor_count_or_identity"),
    ("contract_state","suspended","unverified_suspension_reason"),
    ("cancel_effective_at","2026-09-01T00:00:00Z","cancellation_precedes_membership_start"),
])
def test_membership_scope_fails_closed(field,value,expected):
    x=check(m=membership(**{field:value}))
    assert x["state"]=="HOLD"
    assert expected in x["blockers"]


@pytest.mark.parametrize("field,value,expected",[
    ("membership_id",BUYER,"cross_tenant_or_member_cycle_mismatch"),
    ("tenant_id",BUYER,"cross_tenant_or_member_cycle_mismatch"),
    ("period_start","2026-10-02T00:00:00Z","invoice_monthly_calendar_period_mismatch"),
    ("period_end","2026-11-02T00:00:00Z","invoice_monthly_calendar_period_mismatch"),
    ("membership_price_cents",9900,"invoice_price_drift"),
    ("terms_sha256","f"*64,"invoice_terms_digest_drift"),
    ("invoice_id",None,"settled_cycle_missing_payment_receipts"),
    ("payment_state","NOT_REAL","invalid_payment_state"),
    ("payment_join_state","FORGED_TRUE","settled_cycle_lacks_native_payment_join"),
    ("period_index",-1,"duplicate_or_invalid_billing_cycle_index"),
])
def test_invoice_payment_cross_scope_fails_closed(field,value,expected):
    p=paid(**{field:value})
    x=check(rows=[p])
    assert x["state"]=="HOLD"
    assert expected in x["blockers"]


def test_duplicate_invoice_and_receipt_replay_rejected():
    q=paid(index=1)
    x=check(rows=[paid(),q])
    assert x["state"]=="HOLD"
    assert {"reused_invoice_id","reused_payment_request","reused_settlement_receipt"} <= set(x["blockers"])


def test_duplicate_period_index_rejected():
    x=check(rows=[paid(),paid()])
    assert x["state"]=="HOLD"
    assert "duplicate_or_invalid_billing_cycle_index" in x["blockers"]


def test_more_than_24_cycles_not_read():
    x=check(rows=[paid()]*25)
    assert x["state"]=="HOLD"
    assert "unbounded_membership_renewal_history" in x["blockers"]


def test_bad_clock_and_types_fail_closed():
    with pytest.raises(ValueError,match="timezone_aware_now_required"):
        check(now=datetime(2026,10,20))
    assert check(m={})["state"]=="HOLD"
    assert check(rows=None)["state"]=="RENEWAL_REVIEW_NO_EXECUTION"
    assert check(m=membership(contract_state=["accepted"]))["state"]=="HOLD"
    assert check(m=membership(authorized_corridor_keys=[{"bad":"scope"}]))["state"]=="HOLD"
    assert check(rows=[paid(payment_state=["settled_shape"])])["state"]=="HOLD"


def test_incomplete_monthly_history_never_claims_continuous_renewal():
    x=check(rows=[paid(index=1)],now=datetime(2026,11,15,tzinfo=timezone.utc))
    assert x["state"]=="HOLD"
    assert "missing_prior_monthly_invoice_history" in x["blockers"]


def test_unsent_invoice_renewal_not_new_subscription_mrr():
    x=check(rows=[paid()],now=datetime(2026,11,5,tzinfo=timezone.utc))
    assert x["state"]=="RENEWAL_REVIEW_NO_EXECUTION"
    assert x["hypothetical_current_period_state"]=="CURRENT_MONTH_HAS_NO_PAYMENT_RECORD"
    assert x["actual_paid_revenue_cents"]==0
    assert x["recognized_mrr_cents"]==0
    assert x["renewal_invoices_created"]==0
