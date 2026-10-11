"""Buyer-initiated commercial sales intake: exact approval, consent, identity and no execution."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json

import pytest
from fastapi.testclient import TestClient

from empire_os.digital_avatar_approved_catalog_preview import build_approved_avatar_catalog_preview
from empire_os.first_party_sales_interest import (
    CommercialInterestError, founder_led_commercial_offers, record_founder_led_interest,
)

NOW = datetime(2026, 10, 11, 22, 20, tzinfo=timezone.utc)


def approved_root(tmp_path):
    source = {
        "schema_version": "empire.commercial-product-catalog.v1",
        "generated_at": NOW.isoformat(),
        "execution_authority": "none", "actual_revenue": False,
        "product_count": 0, "products": [],
    }
    price = build_approved_avatar_catalog_preview(source, now=NOW)
    path = tmp_path / "runtime/commercial_proposals/digital_avatar_approved_price_v1.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(price))
    return tmp_path


def params(code="consultancy_opportunity_assessment"):
    return {
        "product_code": code,
        "business_name": "Example Corporation",
        "email": "director@example.test",
        "domain": "example.test",
        "industry": "Professional services",
        "geography": "Greater Manchester",
        "desired_outcome": "We need to improve commercial sales conversion.",
        "contact_consent": True,
        "idempotency_key": "test-deterministic-sale-001",
        "now": NOW,
    }


def test_three_founder_approved_consultancy_offers_are_enquiry_only(tmp_path):
    result=founder_led_commercial_offers(root=tmp_path)
    assert result["count"]==3
    assert [x["approved_price_cents"] for x in result["offers"]]==[250000,750000,300000]
    assert all(x["currency"]=="GBP" for x in result["offers"])
    assert [x["price_interval"] for x in result["offers"]]==["one_time","one_time","monthly"]
    assert result["payment_authority"]=="none"
    assert result["checkout_authorized"] is False
    assert result["actual_revenue"] is False
    assert all(x["binding_terms_ready"] is False for x in result["offers"])


def test_six_prices_after_exact_avatar_policy_approval(tmp_path):
    root=approved_root(tmp_path)
    result=founder_led_commercial_offers(root=root)
    assert result["count"]==6
    avatars=[x for x in result["offers"] if x["offer_family"]=="digital_avatar"]
    assert len(avatars)==3
    assert [x["product_code"] for x in avatars]==[
        "digital_avatar_copilot",
        "digital_avatar_workforce",
        "digital_avatar_white_label_workforce",
    ]
    assert [x["approved_price_cents"] for x in avatars]==[150000,500000,1250000]
    assert [x["implementation_fee_cents"] for x in avatars]==[150000,500000,1500000]
    assert all(x["checkout_enabled"] is False for x in avatars)
    assert all(x["delivery_scope_verified"] is False for x in avatars)


def test_inbound_buyer_prospect_uses_existing_empiredb_atomic_rpc(tmp_path):
    calls=[]
    def existing_db_rpc(method, path, *, payload):
        calls.append((method,path,payload))
        return {"decision":"created","prospect":{"id":"test-uuid-1"}}
    data=record_founder_led_interest(
        root=tmp_path, request=existing_db_rpc, **params()
    )
    assert data["decision"]=="commercial_enquiry_recorded"
    assert data["next_step"]=="FOUNDER_REVIEW"
    assert data["binding_commercial_terms"] is False
    assert data["automated_contact_sent"] is False
    assert data["checkout_authorized"] is False
    assert data["payment_action"] is False
    assert data["actual_revenue"] is False
    assert data["execution_authority"]=="none"
    assert len(calls)==1
    method,path,payload=calls[0]
    assert (method,path)==("POST","/rest/v1/rpc/ingest_prospect_atomic")
    assert payload["p_prospect"]["contact_source"]=="first_party_commercial_sales_enquiry"
    assert payload["p_prospect"]["contacted_status"]=="not_contacted"
    assert payload["p_prospect"]["buy_signal_score"]==0
    evidence=payload["p_evidence"]
    assert evidence["contact_consent_evidence"]["consent_to_contact"] is True
    assert evidence["contact_consent_evidence"]["newsletter_or_ongoing_marketing_consent"] is False
    assert evidence["automatic_followup_authorized"] is False
    assert evidence["binding_terms_ready"] is False
    assert evidence["approved_price_cents"]==250000
    assert evidence["approved_price_currency"]=="GBP"
    assert payload["p_ingest_key"].startswith("commercial-sales:")
    assert payload["p_identity_keys"][0]=="domain:example.test"
    assert payload["p_identity_keys"][1].startswith("email:")
    assert "director@example.test" not in payload["p_identity_keys"][1]


@pytest.mark.parametrize(("key","value"),[
    ("contact_consent",False),
    ("contact_consent",1),
    ("website","spam-link"),
    ("email","private@bad"),
    ("domain","https://bad host.invalid"),
    ("industry",""),
    ("business_name",""),
    ("desired_outcome",""),
    ("idempotency_key","bad"),
    ("product_code","nonexistent"),
])
def test_bad_or_unconsented_input_never_touches_database(tmp_path,key,value):
    data=params()
    data[key]=value
    def fail_db(*args,**kwargs):
        pytest.fail("UNCONSENTED_ENQUIRY_WROTE_TO_EMPIREDB")
    with pytest.raises(CommercialInterestError):
        record_founder_led_interest(root=tmp_path,request=fail_db,**data)


def test_avatar_enquiry_needs_exact_verified_founder_price_record(tmp_path):
    data=params("digital_avatar_copilot")
    with pytest.raises(CommercialInterestError,match="offer_not_approved"):
        record_founder_led_interest(root=tmp_path,request=lambda *a,**k:pytest.fail("DB_WRITE"),**data)
    approved_root(tmp_path)
    calls=[]
    def db(method,path,*,payload):
        calls.append(payload)
        return {"decision":"created","prospect":{"id":"uuid-2"}}
    response=record_founder_led_interest(root=tmp_path,request=db,**data)
    assert response["decision"]=="commercial_enquiry_recorded"
    assert len(calls)==1
    assert calls[0]["p_evidence"]["delivery_scope_verified"] is False
    assert calls[0]["p_evidence"]["costs_or_capacity_verified"] is False


def test_different_offers_never_reuse_same_ingest_key(tmp_path):
    ids=[]
    def db(method,path,*,payload):
        ids.append(payload["p_ingest_key"])
        return {"decision":"existing_identity","prospect":{"id":"same-existing-buyer"}}
    for code in ("consultancy_opportunity_assessment","consultancy_strategy_blueprint"):
        record_founder_led_interest(root=tmp_path,request=db,**params(code))
    assert len(ids)==2 and ids[0]!=ids[1]


def test_failed_canonical_db_proposal_fails_closed_not_fake_received(tmp_path):
    with pytest.raises(CommercialInterestError,match="not_recorded"):
        record_founder_led_interest(
            root=tmp_path,request=lambda *a,**k:{"decision":"not_admitted"},**params()
        )


def test_checkout_service_defaults_binding_order_off(monkeypatch):
    import empire_os.self_serve_checkout_api as api
    monkeypatch.delenv("EMPIRE_SELF_SERVE_BINDING_ORDERS_AUTHORIZED",raising=False)
    monkeypatch.setattr(api,"prepare_checkout_order",lambda **k: pytest.fail("BINDING_ORDER_CREATED"))
    client=TestClient(api.app)
    health=client.get("/health")
    assert health.status_code==200
    assert health.json()["binding_order_creation_authorized"] is False
    assert health.json()["payment_execution"] is False
    result=client.post("/v1/orders",json={
        "product_code":"competitor_search_gap","business_name":"Example",
        "email":"buyer@example.com","target_domain":"example.com",
        "payer_wallet":"0x"+"1"*40,"terms_accepted":True,"idempotency_key":"checkout-test-5555",
    })
    assert result.status_code==503
    assert result.json()["detail"]=="binding_orders_not_authorized"


def test_commercial_api_has_safe_offer_and_consent_schema(monkeypatch,tmp_path):
    import empire_os.self_serve_checkout_api as api
    monkeypatch.setattr(api,"founder_led_commercial_offers",
                        lambda:founder_led_commercial_offers(root=tmp_path))
    client=TestClient(api.app)
    r=client.get("/v1/commercial/offers")
    assert r.status_code==200
    assert r.json()["count"]==3
    assert r.json()["checkout_authorized"] is False
    body={k:v for k,v in params().items() if k!="now"}
    body["contact_consent"]=False
    monkeypatch.setattr(api,"record_founder_led_interest",lambda **kwargs:pytest.fail("NO_CONSENT_DATABASE_WRITE"))
    bad=client.post("/v1/commercial/interests",json=body)
    assert bad.status_code==422


def test_commercial_api_maps_confirmed_intake(monkeypatch):
    import empire_os.self_serve_checkout_api as api
    monkeypatch.setattr(api,"record_founder_led_interest",lambda **kwargs:{
        "decision":"commercial_enquiry_recorded",
        "reference":"abc1","execution_authority":"none","actual_revenue":False,
    })
    body={k:v for k,v in params().items() if k!="now"}
    response=TestClient(api.app).post("/v1/commercial/interests",json=body)
    assert response.status_code==200
    assert response.json()["decision"]=="commercial_enquiry_recorded"
    assert response.json()["actual_revenue"] is False



def _make_verified_intelligence_catalog(tmp_path, *, stale=False):
    stamp = datetime(2026, 9, 1, tzinfo=timezone.utc) if stale else datetime.now(timezone.utc)
    base = {
        "schema_version": "empire.commercial-product-catalog.v1",
        "generated_at": stamp.isoformat(),
        "execution_authority": "none",
        "actual_revenue": False,
    }
    rows = []
    for code, cents in (
        ("competitor_search_gap", 19900),
        ("search_opportunity_map", 24900),
        ("solar_opportunity_map_us", 29900),
        ("technical_search_audit", 29900),
    ):
        rows.append({
            "product_code": code, "product_name": code.replace("_", " ").title(),
            "active": True, "binding_terms_ready": True,
            "catalog_state": "VERIFIED", "version_state": "VERIFIED",
            "billing_model": "one_time",
            "price_basis": {
                "state": "VERIFIED", "currency": "USD",
                "amount_cents": cents,
            },
        })
    base["products"] = rows
    base["product_count"] = len(rows)
    path = tmp_path/"runtime/commercial_catalog/latest.json"
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(base))
    return path


def test_four_existing_one_time_products_enter_founder_led_enquiry_when_orders_held(tmp_path):
    _make_verified_intelligence_catalog(tmp_path)
    view=founder_led_commercial_offers(root=tmp_path)
    assert view["count"]==7
    intelligence=[o for o in view["offers"] if o["offer_family"]=="intelligence_product"]
    assert len(intelligence)==4
    assert [o["approved_price_cents"] for o in intelligence]==[19900,24900,29900,29900]
    assert all(o["delivery_scope_verified"] is True for o in intelligence)
    assert all(o["checkout_enabled"] is False for o in intelligence)
    assert view["checkout_authorized"] is False


def test_stale_catalog_does_not_advertise_intelligence_products(tmp_path):
    _make_verified_intelligence_catalog(tmp_path,stale=True)
    view=founder_led_commercial_offers(root=tmp_path)
    assert view["count"]==3
    assert not any(o["offer_family"]=="intelligence_product" for o in view["offers"])


def test_first_party_sales_enquiry_supports_verified_catalog_product_without_payment(tmp_path):
    _make_verified_intelligence_catalog(tmp_path)
    calls=[]
    def db(method,path,*,payload):
        calls.append(payload)
        return {"decision":"created","prospect":{"id":"existing-canonical-prospect"}}
    response=record_founder_led_interest(
        root=tmp_path,request=db,**params("search_opportunity_map")
    )
    assert response["product_code"]=="search_opportunity_map"
    assert response["payment_action"] is False
    evidence=calls[0]["p_evidence"]
    assert evidence["offer_family"]=="intelligence_product"
    assert evidence["approved_price_cents"]==24900
    assert evidence["binding_terms_ready"] is False
    assert evidence["checkout_authorized"] is False
