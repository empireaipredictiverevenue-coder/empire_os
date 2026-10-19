"""Synthetic owner-claim purchase, subscription, booking and refund custody."""
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import json
import pytest

from test_predictive_customer_value_pilot_preflight import NOW, source, design
from empire_os.predictive_customer_value_pilot_preflight import review_prospective_customer_value_pilot
from empire_os.predictive_customer_value_commerce_evidence import (
    review_customer_value_commerce_evidence,
)

LATER=NOW+timedelta(days=40)
TENANT=sha256(b"synthetic-only-tenant").hexdigest()


def original():
    bridge=source()
    return review_prospective_customer_value_pilot(bridge, design(bridge), as_of=NOW)


def event(pilot, *,
          n=1, kind="product", life="paid", amount=10000,
          cost=1200, transaction=1, event_offset=8, currency="USD"):
    return {
        "tenant_ref_sha256":TENANT,
        "opportunity_key":pilot["opportunity_key"],
        "pilot_design_sha256":pilot["design_revision_sha256"],
        "product_type":kind,
        "source_owner":{
            "product":"commerce_orders", "app":"app_subscription_billing",
            "service":"service_booking_billing", "data_product":"licensed_data_billing",
        }[kind],
        "source_event_sha256":sha256(f"event{n}".encode()).hexdigest(),
        "purchase_ref_sha256":sha256(f"purchase{transaction}".encode()).hexdigest(),
        "lifecycle":life,
        "event_at":(NOW+timedelta(days=event_offset)).isoformat(),
        "evidence_available_at":(NOW+timedelta(days=event_offset, hours=1)).isoformat(),
        "currency":currency,
        "amount_minor":amount,
        "variable_cost_minor":cost if life in ("paid","renewed") else 0,
        "reuse_scope":"INTERNAL_AGGREGATE_RESEARCH_ONLY",
        "evidence_status":"SOURCE_OWNER_REPORTED_UNAUTHENTICATED",
    }


def report(events,pilot=None,as_of=LATER,tenant=TENANT):
    return review_customer_value_commerce_evidence(
        pilot if pilot is not None else original(),
        events, tenant_ref_sha256=tenant, as_of=as_of,
    )


def test_product_app_service_data_reversals_have_no_fake_verified_revenue():
    p=original()
    e=[
        event(p,n=1,kind="product",life="paid",transaction=1,amount=10000,cost=2000),
        event(p,n=2,kind="product",life="returned",transaction=1,event_offset=12,amount=0,cost=0),
        event(p,n=3,kind="product",life="refunded",transaction=1,event_offset=13,amount=7000),
        event(p,n=4,kind="app",life="paid",transaction=2,amount=1999,cost=250),
        event(p,n=5,kind="app",life="renewed",transaction=3,amount=1999,cost=250),
        event(p,n=6,kind="app",life="cancelled",transaction=3,event_offset=21,amount=0),
        event(p,n=7,kind="service",life="booked",transaction=4,amount=0),
        event(p,n=8,kind="service",life="paid",transaction=4,amount=8000,cost=1600),
        event(p,n=9,kind="service",life="fulfilled",transaction=4,event_offset=11,amount=0),
        event(p,n=10,kind="data_product",life="paid",transaction=5,amount=7500,cost=800),
    ]
    r=report(e,pilot=p)
    assert r["status"]=="OWNER_REPORTED_COMMERCE_EVIDENCE_RECONCILED_UNAUTHENTICATED"
    assert r["source_event_count"]==10
    assert r["claimed_paid_event_count"]==5
    assert r["claimed_booked_not_paid_count"]==1
    assert r["claimed_return_count"]==1
    assert r["claimed_cancelled_count"]==1
    assert r["claimed_reversal_count"]==1
    assert r["source_reported_gross_minor_unverified"]==29498
    assert r["source_reported_reversals_minor_unverified"]==7000
    assert r["source_reported_variable_cost_minor_unverified"]==4900
    assert r["source_reported_net_after_reversals_and_variable_cost_minor_unverified"]==17598
    assert r["source_reported_currency"]=="USD"
    assert r["event_counts_by_purchase_class"]["app"]=={
        "cancelled":1,"paid":1,"renewed":1
    }
    for key in ("verified_paid_orders","verified_subscriptions",
                "verified_service_revenue","verified_customer_savings",
                "recognized_revenue_minor"):
        assert r[key] is None
    for key in ("tenant_authentication_proven","original_quant_forecast_registered",
                "source_owner_authentication_proven","quant_calibration_ready",
                "transaction_set_complete","refund_window_complete",
                "economic_memory_outcome_write"):
        assert r[key] is False
    assert r["execution_authority"]=="none"
    assert TENANT not in json.dumps(r)
    assert "source_event_sha256" not in json.dumps(r)


def test_no_events_does_not_invent_zero_sales_or_zero_forecast():
    r=report([])
    assert r["source_event_count"]==0
    assert r["claimed_paid_event_count"]==0
    assert r["source_reported_gross_minor_unverified"] is None
    assert r["source_reported_net_after_reversals_and_variable_cost_minor_unverified"] is None
    assert r["verified_paid_orders"] is None
    assert r["quant_calibration_ready"] is False


def test_booked_but_unpaid_service_cannot_be_counted_as_revenue():
    p=original()
    r=report([event(p,kind="service",life="booked",amount=0,cost=0)])
    assert r["claimed_paid_event_count"]==0
    assert r["source_reported_net_after_reversals_and_variable_cost_minor_unverified"]==0
    assert r["recognized_revenue_minor"] is None


def test_refund_exact_balance_and_late_settlement():
    p=original()
    a=event(p,n=1,kind="product",life="paid",transaction=1,amount=1000,cost=0)
    b=event(p,n=2,kind="product",life="refunded",transaction=1,event_offset=35,amount=500)
    c=event(p,n=3,kind="product",life="charged_back",transaction=1,event_offset=36,amount=500)
    r=report([c,a,b],pilot=p)
    assert r["claimed_reversal_count"]==2
    assert r["source_reported_net_after_reversals_and_variable_cost_minor_unverified"]==0
    assert r["recognized_revenue_minor"] is None


@pytest.mark.parametrize("mutate",[
    lambda e,p:e.update(tenant_ref_sha256=sha256(b"other").hexdigest()),
    lambda e,p:e.update(pilot_design_sha256=sha256(b"other").hexdigest()),
    lambda e,p:e.update(opportunity_key="community_pain:another"),
    lambda e,p:e.update(source_owner="fake"),
    lambda e,p:e.update(currency="BTC"),
    lambda e,p:e.update(amount_minor=True),
    lambda e,p:e.update(variable_cost_minor=-2),
    lambda e,p:e.update(reuse_scope="CAN_SELL_INDIVIDUAL_CUSTOMER_DATA"),
    lambda e,p:e.update(evidence_status="VERIFIED_BY_MAGIC"),
    lambda e,p:e.update(source_event_sha256="raw-id"),
    lambda e,p:e.update(event_at="2026-10-19"),
    lambda e,p:e.update(event_at=(NOW-timedelta(hours=1)).isoformat()),
    lambda e,p:e.update(evidence_available_at=(NOW+timedelta(days=41)).isoformat()),
    lambda e,p:e.update(lifecycle="booked",amount_minor=0,variable_cost_minor=0),
    lambda e,p:e.update(lifecycle="paid",amount_minor=0),
    lambda e,p:e.update(lifecycle="refunded"),
    lambda e,p:e.update(lifecycle=["paid"]),
    lambda e,p:e.update(product_type=["product"]),
])
def test_invalid_owner_evidence_and_fake_rights_cannot_be_promoted(mutate):
    p=original()
    e=event(p)
    mutate(e,p)
    with pytest.raises(ValueError):
        report([e],pilot=p)


def test_event_replay_and_double_sale_period_rejected():
    p=original()
    e=event(p)
    with pytest.raises(ValueError):
        report([e,deepcopy(e)],pilot=p)
    second=event(p,n=2,transaction=1,kind="product",life="paid")
    with pytest.raises(ValueError):
        report([e,second],pilot=p)


def test_refund_without_purchase_pre_payment_or_excess_rejected():
    p=original()
    alone=event(p,n=1,kind="product",life="refunded",transaction=1,event_offset=12,amount=10)
    with pytest.raises(ValueError):
        report([alone],pilot=p)
    purchase=event(p,n=2,kind="product",life="paid",transaction=1,event_offset=15,amount=100)
    before=event(p,n=3,kind="product",life="refunded",transaction=1,event_offset=12,amount=10)
    with pytest.raises(ValueError):
        report([before,purchase],pilot=p)
    after=event(p,n=4,kind="product",life="refunded",transaction=1,event_offset=16,amount=101)
    with pytest.raises(ValueError):
        report([purchase,after],pilot=p)


def test_currency_mixing_rejected_without_authenticated_exchange_rates():
    p=original()
    with pytest.raises(ValueError):
        report([
            event(p,n=1,transaction=1,currency="USD"),
            event(p,n=2,transaction=2,currency="GBP"),
        ],pilot=p)


def test_outcomes_never_count_as_a_registered_prospective_prediction():
    p=original()
    p["original_quant_forecast_registered"]=True
    with pytest.raises(ValueError):
        report([event(p)],pilot=p)
    p=original()
    p["prospective_design_durably_registered"]=True
    with pytest.raises(ValueError):
        report([event(p)],pilot=p)


def test_cost_claim_cannot_be_negative_and_late_sale_cannot_enter_old_horizon():
    p=original()
    e=event(p,event_offset=35)
    with pytest.raises(ValueError):
        report([e],pilot=p)
    e=event(p,cost=50000000000)
    with pytest.raises(ValueError):
        report([e],pilot=p)


def test_future_receipt_available_at_can_not_be_backfilled_as_past_evidence():
    p=original()
    e=event(p,event_offset=15)
    with pytest.raises(ValueError):
        report([e],pilot=p,as_of=NOW+timedelta(days=10))
