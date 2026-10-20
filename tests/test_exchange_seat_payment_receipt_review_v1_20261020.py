"""Cross-table USDT/seat subscription receipts never create real entitlements."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import pytest

from empire_os.exchange_seat_payment_receipt_review_v1 import (
    review_exchange_membership_payment_join,
)

NOW=datetime(2026,10,20,18,40,tzinfo=timezone.utc)
BUYER="22222222-2222-4222-8222-222222222222"
ORDER="33333333-3333-4333-8333-333333333333"
REQ="44444444-4444-4444-8444-444444444444"
TERMS="a"*64
PAYER="0x"+"b"*40
TREASURY="0x"+"c"*40


def records():
    return dict(
        order=dict(
            id=ORDER,buyer_id=BUYER,state="invoiced",price_cents=24900,quantity=1,
            commercial_payload=dict(
                purchase_purpose="exchange_seat_monthly_membership",
                exchange_seat_product_code="exchange_seat_growth",
                price_currency="USD",
                membership_period_start="2026-10-01T00:00:00Z",
                membership_period_end="2026-11-01T00:00:00Z",
                commercial_terms_sha256=TERMS,
            ),
        ),
        request=dict(
            id=REQ,buyer_id=BUYER,fulfilment_order_id=ORDER,
            status="approved",settlement_mode="direct",
            approved_by="independent_payment_operator",
            approved_at="2026-10-19T12:00:00Z",
            expires_at="2026-10-22T12:00:00Z",
            commercial_terms_sha256=TERMS,
            amount_usdt="249.000000000000000000",
            min_block_number=5000,
            payer_address=PAYER,treasury_address=TREASURY,
        ),
        evidence=dict(
            request_id=REQ,fulfilment_order_id=ORDER,chain_id=56,
            token_contract="0x55d398326f99059ff775485246999027b3197955",
            confirmations=12,block_number=6000,
            transaction_hash="0x"+"f"*64,
            commercial_terms_sha256=TERMS,
            amount_raw="249000000000000000000",
            verified_at="2026-10-20T12:00:00Z",
            sender_address=PAYER,treasury_address=TREASURY,
        ),
        finance_quote=dict(
            fulfilment_order_id=ORDER,buyer_id=BUYER,
            monthly_usd_price_cents=24900,
            amount_usdt="249.000000000000000000",
            membership_period_start="2026-10-01T00:00:00Z",
            membership_period_end="2026-11-01T00:00:00Z",
            commercial_terms_sha256=TERMS,
            quote_basis="finance_reviewed_usdt_conversion",
            rate_evidence_ref="independent-finance-quote-001",
        ),
    )


def assess(**kwargs):
    return review_exchange_membership_payment_join(now=NOW,**kwargs)


def test_consistent_synthetic_order_payment_does_not_activate_seat():
    result=assess(**records())
    assert result["state"]=="CROSS_TABLE_PAYMENT_RECEIPT_SHAPE_CONSISTENT_NOT_AUTHENTICATED"
    assert result["order_request_evidence_quote_matched_within_input"] is True
    assert result["monthly_catalog_price_cents"]==24900
    assert result["subscription_entitlement_authorized"] is False
    assert result["seat_activated"] is False
    assert result["actual_paid_subscription_count_verified"]==0
    assert result["actual_mrr_cents_recognized"]==0
    assert result["lead_delivery_authorized"] is False
    assert result["database_writes"] is False
    serial=json.dumps(result)
    assert BUYER not in serial and ORDER not in serial and REQ not in serial
    assert PAYER not in serial and TREASURY not in serial
    assert "0x"+"f"*64 not in serial


@pytest.mark.parametrize("name,mutate,expected",[
    ("wrong_buyer",lambda x:x["request"].update(buyer_id="55555555-5555-4555-8555-555555555555"),"payment_request_order_buyer_mismatch"),
    ("wrong_order",lambda x:x["evidence"].update(fulfilment_order_id="55555555-5555-4555-8555-555555555555"),"payment_evidence_request_order_mismatch"),
    ("wrong_plan",lambda x:x["order"]["commercial_payload"].update(exchange_seat_product_code="exchange_seat_fake"),"order_not_specific_exchange_seat_plan"),
    ("wrong_price",lambda x:x["order"].update(price_cents=9900),"membership_product_price_or_quantity_mismatch"),
    ("wrong_quantity",lambda x:x["order"].update(quantity=2),"membership_product_price_or_quantity_mismatch"),
    ("wrong_purpose",lambda x:x["order"]["commercial_payload"].update(purchase_purpose="single_lead_sale"),"not_a_valid_monthly_membership_order"),
    ("wrong_terms",lambda x:x["evidence"].update(commercial_terms_sha256="e"*64),"commercial_terms_hash_mismatch"),
    ("wrong_chain",lambda x:x["evidence"].update(chain_id=1),"wrong_bsc_chain_token_or_settlement"),
    ("wrong_token",lambda x:x["evidence"].update(token_contract="0x"+"d"*40),"wrong_bsc_chain_token_or_settlement"),
    ("wrong_mode",lambda x:x["request"].update(settlement_mode="escrow"),"wrong_bsc_chain_token_or_settlement"),
    ("11_confs",lambda x:x["evidence"].update(confirmations=11),"bsc_finality_or_block_floor_missing"),
    ("wrong_amount",lambda x:x["evidence"].update(amount_raw="199000000000000000000"),"bsc_payment_amount_quote_mismatch"),
    ("wrong_quote",lambda x:x["finance_quote"].update(monthly_usd_price_cents=99900),"usd_plan_price_quote_mismatch"),
    ("no_rate",lambda x:x["finance_quote"].update(rate_evidence_ref=""),"finance_exchange_rate_receipt_not_provided"),
    ("no_finance_scope",lambda x:x["finance_quote"].update(quote_basis="guess"),"finance_quote_rate_evidence_missing"),
    ("wrong_treasury",lambda x:x["evidence"].update(treasury_address="0x"+"e"*40),"bsc_treasury_mismatch"),
    ("wrong_payer",lambda x:x["evidence"].update(sender_address="0x"+"e"*40),"bsc_payer_mismatch"),
    ("expired_membership",lambda x:x["order"]["commercial_payload"].update(membership_period_end="2026-10-19T00:00:00Z"),"membership_period_not_current"),
    ("long_period",lambda x:x["order"]["commercial_payload"].update(membership_period_end="2026-12-01T00:00:00Z"),"membership_period_not_monthly"),
    ("late_payment",lambda x:x["evidence"].update(verified_at="2026-10-23T00:00:00Z"),"settlement_outside_approved_request_window"),
    ("unapproved",lambda x:x["request"].update(status="pending"),"missing_payment_operator_approval"),
])
def test_mismatched_native_receipts_fail_closed(name,mutate,expected):
    values=records()
    mutate(values)
    result=assess(**values)
    assert result["state"]=="HOLD",name
    assert expected in result["blockers"],(name,result["blockers"])
    assert result["actual_mrr_cents_recognized"]==0
    assert result["subscription_entitlement_authorized"] is False


def test_missing_native_rows_and_invalid_aware_time():
    x=records()
    x["evidence"]=None
    assert assess(**x)["state"]=="HOLD"
    with pytest.raises(ValueError,match="timezone_aware_now_required"):
        review_exchange_membership_payment_join(
            **records(),now=datetime(2026,10,20),
        )


def test_legacy_subscription_row_cannot_stand_in_for_native_payment():
    source=records()
    source["evidence"]={
        "status":"active","stripe_subscription_id":"old-stripe-id",
        "buyer_id":BUYER,"monthly_price_cents":24900,
    }
    result=assess(**source)
    assert result["state"]=="HOLD"
    assert result["subscription_entitlement_authorized"] is False
