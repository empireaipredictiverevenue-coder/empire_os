"""Pure, non-production buyer order → BSC → report review gauntlet."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime,timedelta,timezone
from uuid import uuid4
import pytest

from empire_os.paid_search_fulfilment_review import (
    review_paid_search_order as review,
    _verified_payment, _domain,
)
from empire_os.search_intelligence.products import get_search_product

NOW=datetime(2026,10,14,11,tzinfo=timezone.utc)
OID=str(uuid4()); RID=str(uuid4()); BID=str(uuid4())
PAYER="0x"+"1"*40
TREASURY="0x1339b487046b0ad924a10c20b1791608ea8595a8"
TOKEN="0x55d398326f99059ff775485246999027b3197955"
TERMS="a"*64


def fixture(sku="competitor_search_gap"):
    price={"competitor_search_gap":19900,
           "search_opportunity_map":24900,
           "technical_search_audit":29900,
           "solar_opportunity_map_us":29900}[sku]
    order={
        "id":OID,"buyer_id":BID,"price_cents":price,"state":"accepted",
        "commercial_payload":{
            "product_code":sku,
            "commercial_terms_sha256":TERMS,
            "payer_wallet":PAYER,
            "buyer_terms_accepted":True,
            "settlement_mode":"direct",
        },
        "delivery_payload":{
            "target_domain":"example.com",
            "delivery_mode":"email_and_secure_link",
            "automatic_fulfilment_requested":False,
        },
    }
    payment={
        "id":RID,"buyer_id":BID,"fulfilment_order_id":OID,
        "settlement_mode":"direct","commercial_terms_sha256":TERMS,
        "status":"approved",
        "approved_by":"independent-human",
        "approved_at":NOW-timedelta(minutes=30),
        "expires_at":NOW+timedelta(hours=2),
        "payer_address":PAYER,"treasury_address":TREASURY,
        "amount_usdt":str(price/100),
    }
    evidence={
        "id":str(uuid4()),"request_id":RID,
        "fulfilment_order_id":OID,"chain_id":56,
        "token_contract":TOKEN,"transaction_hash":"0x"+"b"*64,
        "block_hash":"0x"+"c"*64,"block_number":1000,"log_index":0,
        "amount_raw":str(price*10**16),"confirmations":12,
        "verified_at":NOW-timedelta(minutes=5),
        "sender_address":PAYER,"treasury_address":TREASURY,
        "commercial_terms_sha256":TERMS,
    }
    report={}
    product=get_search_product(sku)
    if product:
        for section in product.deliverables:
            report[section]={
                "source_refs":["first_party_search_observation:123"],
                "observed_at":(NOW-timedelta(hours=1)).isoformat(),
                "synthetic":False,
                "value":{"finding":"observed record requires human review"},
            }
    return order,payment,evidence,report


@pytest.mark.parametrize("sku",[
    "competitor_search_gap","search_opportunity_map",
    "technical_search_audit",
])
def test_all_three_standard_products_only_generate_review_packet(sku):
    order,payment,evidence,report=fixture(sku)
    out=review(order=order,payment=payment,evidence=evidence,
               report_evidence=report,now=NOW)
    assert out["decision"]=="READY_FOR_HUMAN_REPORT_REVIEW"
    assert out["report"]["product"]["key"]==sku
    assert out["report"]["site"]=="https://example.com"
    assert out["report"]["unavailable_sections"]==0
    assert out["report"]["synthetic_metrics"]==0
    assert out["source_verified_by_this_function"] is False
    assert out["delivery_authorized"] is False
    assert out["outbound_sent"] is False
    assert out["revenue_recognized"] is False
    assert out["order_mutated"] is False
    assert "email" not in str(out)


@pytest.mark.parametrize("field,value",[
    ("status","pending"),("status","expired"),("approved_by",None),
    ("amount_usdt","198.99"),("settlement_mode","escrow"),
    ("buyer_id",str(uuid4())),("payer_address","0x"+"2"*40),
    ("treasury_address","0x"+"3"*40),
    ("commercial_terms_sha256","e"*64),
    ("approved_at",NOW+timedelta(minutes=1)),
])
def test_payment_tampering_never_yields_review_ready(field,value):
    o,p,e,r=fixture()
    p[field]=value
    assert review(order=o,payment=p,evidence=e,report_evidence=r,now=NOW)["decision"]=="HOLD_CANONICAL_PAYMENT_EVIDENCE"


@pytest.mark.parametrize("field,value",[
    ("confirmations",11),("confirmations",True),
    ("chain_id",97),("token_contract","0x"+"f"*40),
    ("amount_raw","100"),("sender_address","0x"+"2"*40),
    ("request_id",str(uuid4())),("fulfilment_order_id",str(uuid4())),
    ("treasury_address","0x"+"2"*40),
    ("commercial_terms_sha256","d"*64),
    ("transaction_hash","0x0"),("block_hash","0x0"),
    ("log_index",-1),("id",None),
    ("verified_at",NOW+timedelta(hours=1)),
])
def test_evidence_tampering_or_insufficient_confirmations_hold(field,value):
    o,p,e,r=fixture()
    e[field]=value
    result=review(order=o,payment=p,evidence=e,report_evidence=r,now=NOW)
    assert result["decision"]=="HOLD_CANONICAL_PAYMENT_EVIDENCE"
    assert result["report"] is None


@pytest.mark.parametrize("missing",["competitor_presence_map","query_gap_findings"])
def test_missing_report_section_is_not_customer_delivery(missing):
    o,p,e,r=fixture()
    del r[missing]
    out=review(order=o,payment=p,evidence=e,report_evidence=r,now=NOW)
    assert out["decision"]=="HOLD_OBSERVED_REPORT_EVIDENCE"
    assert out["report"] is None
    assert out["delivery_authorized"] is False


@pytest.mark.parametrize("bad",[
    {"synthetic":True},{"source_refs":[]},{"observed_at":"2099-01-01T00:00:00+00:00"},
    {"value":None},{"source_refs":[""]},{"observed_at":"not-a-timestamp"},
])
def test_report_provenance_is_required(bad):
    o,p,e,r=fixture()
    r["query_gap_findings"].update(bad)
    out=review(order=o,payment=p,evidence=e,report_evidence=r,now=NOW)
    assert out["decision"]=="HOLD_OBSERVED_REPORT_EVIDENCE"


@pytest.mark.parametrize("bad",[
    {"state":"cancelled"},
    {"price_cents":20000},
    {"commercial_payload":{"product_code":"unapproved"}},
    {"commercial_payload":{"product_code":"competitor_search_gap","buyer_terms_accepted":False}},
    {"delivery_payload":{"target_domain":"evil.com/path"}},
])
def test_wrong_order_scope_or_terms_holds(bad):
    o,p,e,r=fixture()
    o.update(bad)
    out=review(order=o,payment=p,evidence=e,report_evidence=r,now=NOW)
    assert out["decision"]!="READY_FOR_HUMAN_REPORT_REVIEW"


def test_solar_builder_is_not_bound_to_buyer_order_by_domain_only():
    o,p,e,r=fixture("solar_opportunity_map_us")
    fake={"offer":{"product_code":"solar_opportunity_map_us","country_code":"US"},
          "prospect":{"website":"https://example.com"}}
    out=review(order=o,payment=p,evidence=e,solar_payload=fake,now=NOW)
    assert out["decision"]=="HOLD_SOLAR_ORDER_PROSPECT_BINDING"
    assert out["solar_artifact_matches_domain"] is True
    assert out["report"] is None
    assert out["delivery_authorized"] is False


def test_missing_payment_or_order_holds_and_never_runs_or_writes():
    o,p,e,r=fixture()
    assert review(order=None,payment=p,evidence=e,report_evidence=r)["decision"]=="HOLD_ORDER"
    assert review(order=o,payment=None,evidence=e,report_evidence=r)["decision"]=="HOLD_CANONICAL_PAYMENT_EVIDENCE"
    assert review(order=o,payment=p,evidence=None,report_evidence=r)["decision"]=="HOLD_CANONICAL_PAYMENT_EVIDENCE"


def test_no_side_effects_mutate_caller_records():
    o,p,e,r=fixture()
    before=deepcopy((o,p,e,r))
    review(order=o,payment=p,evidence=e,report_evidence=r,now=NOW)
    assert (o,p,e,r)==before


def test_domain_strict_and_no_external_fetch():
    assert _domain("example.com")=="example.com"
    for value in ("example.com/path","https://example.com", "invalid",None):
        assert _domain(value) is None


def test_payment_proof_after_payment_request_expiry_is_not_delivery_ready():
    order,payment,evidence,report=fixture()
    payment["expires_at"]=NOW-timedelta(minutes=15)
    out=review(order=order,payment=payment,evidence=evidence,
               report_evidence=report,now=NOW)
    assert out["decision"]=="HOLD_CANONICAL_PAYMENT_EVIDENCE"
    assert out["delivery_authorized"] is False


def test_expected_catalog_cost_is_not_actual_delivery_proof():
    order,payment,evidence,report=fixture()
    order["acquisition_cost_cents"]=2000
    order["fulfilment_cost_cents"]=3000
    result=review(order=order,payment=payment,evidence=evidence,
                  report_evidence=report,now=NOW)
    assert result["decision"]=="READY_FOR_HUMAN_REPORT_REVIEW"
    assert result["revenue_recognized"] is False
    assert result["delivery_authorized"] is False
    assert "actual_cost" not in result
