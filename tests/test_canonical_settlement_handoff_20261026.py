"""Exact BSC USDT financial continuity, no chain RPC or money moved."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime,timezone
import pytest

from empire_os.canonical_prospect_tenant_handoff import ProspectHandoffHold
from empire_os.canonical_settlement_handoff import review_fulfilment_payment_settlement
from tests.test_canonical_fulfilment_handoff_20261026 import fixtures, NOW

TX="0x"+"a"*64
TERM="a"*64
PAYER="0x"+"b"*40
TREASURY="0x"+"c"*40
TOKEN="0x55d398326f99059ff775485246999027b3197955"
REQ="00000000-0000-0000-0000-0000000000d1"
PROOF="00000000-0000-0000-0000-0000000000d2"
ESCROW="00000000-0000-0000-0000-0000000000d3"
REVENUE="00000000-0000-0000-0000-0000000000d4"
OTHER="00000000-0000-0000-0000-0000000000e1"

def inputs(mode="direct", *, with_revenue=True):
    from empire_os.canonical_fulfilment_handoff import review_accepted_order_delivery
    accepted,order,outcomes=fixtures()
    delivered=review_accepted_order_delivery(accepted,order,outcomes,as_of=NOW)
    request={
        "id":REQ,"buyer_id":delivered["buyer_id"],
        "fulfilment_order_id":order["id"],
        "status":"approved","approved_by":"original-buyer-approver",
        "approved_at":"2026-10-26T11:15:00+00:00",
        "expires_at":"2026-10-30T12:00:00+00:00",
        "settlement_mode":mode,"commercial_terms_sha256":TERM,
        "amount_usdt":"120","treasury_address":TREASURY,
        "min_block_number":20000000,
    }
    evidence={
        "id":PROOF,"transaction_hash":TX,
        "confirmations":15,"verified_at":"2026-10-26T13:15:00+00:00",
        "block_number":20000001,"amount_raw":120 * 10**18,
    }
    if mode=="direct":
        evidence.update(request_id=REQ,fulfilment_order_id=order["id"],
                        chain_id=56,token_contract=TOKEN,
                        commercial_terms_sha256=TERM,treasury_address=TREASURY)
        escrow=None
        source="direct_payment"
    else:
        escrow={"id":ESCROW,"request_id":REQ,"status":"released",
                "commercial_terms_sha256":TERM,"amount_raw":120 * 10**18}
        evidence.update(agreement_id=ESCROW,action="released")
        source="escrow_release"
    cost={"fulfilment_order_id":order["id"],"actual_cost_ready":True,
          "acquisition_cost":{"evidence_id":"fixture:acquisition-cost",
                              "source_type":"provider_invoice","amount_cents":2000,
                              "observed_at":"2026-10-26T12:00:00+00:00"},
          "fulfilment_cost":{"evidence_id":"fixture:fulfilment-cost",
                              "source_type":"internal_actual","amount_cents":5000,
                              "observed_at":"2026-10-26T12:10:00+00:00"}}
    revenue={
        "id":REVENUE,"event_type":"revenue_recognized",
        "fulfilment_order_id":order["id"],
        "buyer_id":delivered["buyer_id"],"opportunity_id":delivered["opportunity_id"],
        "channel":"bsc_usdt","idempotency_key":"revenue:"+order["id"]+":v1",
        "amount_cents":12000,"cost_cents":7000,"margin_cents":5000,
        "occurred_at":"2026-10-26T13:30:00+00:00",
        "payload":{
            "settlement_source":source,"payment_request_id":REQ,"evidence_id":PROOF,
            "transaction_hash":TX,"commercial_terms_sha256":TERM,
            "settlement_asset":"USDT","settlement_chain":"BSC",
            "actual_revenue":True,"actual_cost_evidence_verified":True,
            "actual_cost_evidence":cost,
        }
    }
    return delivered,order,request,evidence,dict(
        escrow_agreement=escrow,revenue_event=revenue if with_revenue else None)

def run(args):
    return review_fulfilment_payment_settlement(*args[:4],as_of=NOW,**args[4])

@pytest.mark.parametrize("mode",("direct","escrow"))
def test_complete_order_payment_and_original_recognizer_event_coherence(mode):
    v=run(inputs(mode))
    assert v["ledger_payment_link_consistent"] is True
    assert v["revenue_event_consistent"] is True
    assert v["recognized_revenue_event_ref"].endswith(REVENUE)
    assert v["settlement_source_reported"] == ("direct_payment" if mode=="direct" else "escrow_release")
    assert v["approved_price_cents"]==12000
    assert v["reported_actual_cost_evidence_refs"]==[
        "canonical:commercial_evidence_registry:fixture:acquisition-cost",
        "canonical:commercial_evidence_registry:fixture:fulfilment-cost",
    ]
    assert v["status"]=="INJECTED_FINANCIAL_LINEAGE_COHERENCE_ONLY"
    for k in ("payment_receipt_independently_verified_here",
              "blockchain_finality_independently_verified_here",
              "refund_and_dispute_census_complete_here",
              "actual_costs_independently_verified_here",
              "revenue_recognition_independently_verified_here",
              "economic_memory_authorized","payments_executed",
              "outbound_authorized","database_writes"):
        assert v[k] is False

def test_approved_payment_without_revenue_event_never_counts_revenue():
    v=run(inputs(with_revenue=False))
    assert v["ledger_payment_link_consistent"] is True
    assert v["revenue_event_consistent"] is False
    assert v["recognized_revenue_event_ref"] is None
    assert v["reported_actual_cost_evidence_refs"] is None
    assert v["revenue_recognition_independently_verified_here"] is False

@pytest.mark.parametrize("change,error",[
    (lambda a:a[0].update(delivery_record_coherence_verified=False),"UNTRUSTED_DELIVERY_HANDOFF"),
    (lambda a:a[0].update(outbound_authorized=True),"UNTRUSTED_DELIVERY_HANDOFF"),
    (lambda a:a[1].update(buyer_id=OTHER),"CROSS_TENANT_BUYER_OR_OPPORTUNITY_SETTLEMENT_REJECTED"),
    (lambda a:a[2].update(buyer_id=OTHER),"CROSS_TENANT_BUYER_OR_OPPORTUNITY_SETTLEMENT_REJECTED"),
    (lambda a:a[2].update(fulfilment_order_id=OTHER),"CROSS_ORDER_SETTLEMENT_REJECTED"),
    (lambda a:a[2].update(status="pending"),"ORIGINAL_APPROVED_BUYER_PAYMENT_REQUEST_REQUIRED"),
    (lambda a:a[2].update(amount_usdt="121"),"UNMATCHED_APPROVED_PAYMENT_AMOUNT"),
    (lambda a:a[2].update(amount_usdt=120.0),"UNMATCHED_APPROVED_PAYMENT_AMOUNT"),
    (lambda a:a[2].update(commercial_terms_sha256="b"*64),"SETTLEMENT_COMMERCIAL_TERMS_MISMATCH"),
    (lambda a:a[2].update(approved_at="2026-10-26T13:30:00+00:00"),"PAYMENT_VERIFICATION_PREDATES_APPROVAL"),
    (lambda a:a[2].update(approved_at="2026-10-26T10:00:00+00:00"),"PAYMENT_REQUEST_PREDATES_BUYER_ACCEPTANCE"),
    (lambda a:a[2].update(expires_at="2026-10-26T12:00:00+00:00"),"PAYMENT_VERIFICATION_AFTER_APPROVED_EXPIRY"),
    (lambda a:a[3].update(request_id=OTHER),"INVALID_DIRECT_BSC_USDT_RECEIPT_BINDING"),
    (lambda a:a[3].update(chain_id=1),"INVALID_DIRECT_BSC_USDT_RECEIPT_BINDING"),
    (lambda a:a[3].update(confirmations=2),"EXACT_BSC_TRANSACTION_RECEIPT_REQUIRED"),
    (lambda a:a[3].update(amount_raw=119*10**18),"UNMATCHED_BSC_TRANSFER_AMOUNT_OR_BLOCK"),
    (lambda a:a[3].update(block_number=19999999),"INVALID_DIRECT_BSC_USDT_RECEIPT_BINDING"),
    (lambda a:a[3].update(verified_at="2026-11-01T13:00:00+00:00"),"FUTURE_OR_NAIVE_SETTLEMENT_TIMESTAMP"),
    (lambda a:a[3].update(transaction_hash="wrong"),"EXACT_BSC_TRANSACTION_RECEIPT_REQUIRED"),
    (lambda a:a[4]["revenue_event"].update(buyer_id=OTHER),"CROSS_TENANT_BUYER_OR_OPPORTUNITY_SETTLEMENT_REJECTED"),
    (lambda a:a[4]["revenue_event"].update(idempotency_key="other"),"CANONICAL_REVENUE_EVENT_SETTLEMENT_MISMATCH"),
    (lambda a:a[4]["revenue_event"]["payload"].update(evidence_id=OTHER),"CANONICAL_REVENUE_EVENT_SETTLEMENT_MISMATCH"),
    (lambda a:a[4]["revenue_event"].update(amount_cents=12001),"UNRECONCILED_RECOGNIZED_REVENUE_MARGINS"),
    (lambda a:a[4]["revenue_event"].update(margin_cents=4999),"UNRECONCILED_RECOGNIZED_REVENUE_MARGINS"),
    (lambda a:a[4]["revenue_event"]["payload"]["actual_cost_evidence"]["acquisition_cost"].update(amount_cents=3000),"UNRECONCILED_RECOGNIZED_REVENUE_MARGINS"),
    (lambda a:a[4]["revenue_event"].update(occurred_at="2026-10-26T11:00:00+00:00"),"REVENUE_EVENT_PREDATES_PAYMENT_VERIFICATION"),
])
def test_wrong_cross_order_replay_price_cost_or_future_records_fail_closed(change,error):
    a=list(inputs())
    change(a)
    with pytest.raises(ProspectHandoffHold,match=error):
        run(a)

def test_any_known_refund_dispute_or_reversal_requires_fresh_owner_review():
    a=list(inputs())
    a[4]["reversals"]=[{"fulfilment_order_id":a[1]["id"],"action":"refunded"}]
    with pytest.raises(ProspectHandoffHold,match="RECORDED_REVERSAL_OR_DISPUTE_REVIEW_REQUIRED"):
        run(a)

@pytest.mark.parametrize("mod,error",[
    (lambda a:a[4]["escrow_agreement"].update(status="refunded"),"RELEASED_ESCROW_ORDER_BINDING_REQUIRED"),
    (lambda a:a[4]["escrow_agreement"].update(request_id=OTHER),"RELEASED_ESCROW_ORDER_BINDING_REQUIRED"),
    (lambda a:a[3].update(action="funded"),"RELEASED_ESCROW_ORDER_BINDING_REQUIRED"),
    (lambda a:a[3].update(agreement_id=OTHER),"RELEASED_ESCROW_ORDER_BINDING_REQUIRED"),
    (lambda a:a[4]["escrow_agreement"].update(amount_raw=110*10**18),"RELEASED_ESCROW_ORDER_BINDING_REQUIRED"),
])
def test_escrow_release_is_not_escrow_funding_or_refund(mod,error):
    a=list(inputs("escrow"))
    mod(a)
    with pytest.raises(ProspectHandoffHold,match=error):
        run(a)


def test_original_postgresql_numeric_decimal_and_timestamptz_adapters():
    from decimal import Decimal
    from datetime import datetime
    for mode in ("direct","escrow"):
        a=list(inputs(mode))
        a[2]["amount_usdt"]=Decimal("120.000000000000000000")
        a[2]["expires_at"]=datetime.fromisoformat(a[2]["expires_at"])
        a[3]["amount_raw"]=Decimal(120*10**18)
        a[3]["verified_at"]=datetime.fromisoformat(a[3]["verified_at"])
        if mode=="escrow":
            a[4]["escrow_agreement"]["amount_raw"]=Decimal(120*10**18)
        report=run(a)
        assert report["ledger_payment_link_consistent"] is True
        assert report["revenue_recognition_independently_verified_here"] is False


def test_float_payment_base_units_cannot_be_used_as_chain_evidence():
    a=list(inputs())
    a[3]["amount_raw"]=float(120*10**18)
    with pytest.raises(ProspectHandoffHold,match="UNMATCHED_BSC_TRANSFER_AMOUNT_OR_BLOCK"):
        run(a)


def test_negative_margin_cannot_be_recognized_under_original_sql_contract():
    a=list(inputs())
    cost=a[4]["revenue_event"]["payload"]["actual_cost_evidence"]
    cost["acquisition_cost"]["amount_cents"]=10000
    cost["fulfilment_cost"]["amount_cents"]=4000
    a[4]["revenue_event"]["cost_cents"]=14000
    a[4]["revenue_event"]["margin_cents"]=-2000
    with pytest.raises(ProspectHandoffHold,match="UNRECONCILED_RECOGNIZED_REVENUE_MARGINS"):
        run(a)


def test_reused_cost_receipt_or_cost_later_than_recognition_rejected():
    a=list(inputs())
    cost=a[4]["revenue_event"]["payload"]["actual_cost_evidence"]
    cost["fulfilment_cost"]["evidence_id"]=cost["acquisition_cost"]["evidence_id"]
    with pytest.raises(ProspectHandoffHold,match="DUPLICATE_ACTUAL_COST_EVIDENCE_ID"):
        run(a)
    a=list(inputs())
    cost=a[4]["revenue_event"]["payload"]["actual_cost_evidence"]
    cost["fulfilment_cost"]["observed_at"]="2026-10-26T13:45:00+00:00"
    with pytest.raises(ProspectHandoffHold,match="ACTUAL_COST_OBSERVED_AFTER_REVENUE_EVENT"):
        run(a)


@pytest.mark.parametrize("invalid", ({}, [], 0, True, "", "  ", " invoice-01 "))
def test_invalid_cost_evidence_id_never_causes_unhandled_type_error(invalid):
    a=list(inputs())
    cost=a[4]["revenue_event"]["payload"]["actual_cost_evidence"]
    cost["acquisition_cost"]["evidence_id"]=invalid
    with pytest.raises(ProspectHandoffHold, match="ORIGINAL_ACTUAL_COST_RECEIPT_MISSING"):
        run(a)
