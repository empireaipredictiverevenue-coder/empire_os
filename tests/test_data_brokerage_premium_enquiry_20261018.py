"""Premium discovery consent → exact existing EmpireDB RPC; never paid contract.

All POST tests use a fake RPC and an isolated FastAPI application.
No request here calls the production gateway, mailbox or source database.
"""
from __future__ import annotations
from datetime import datetime,timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from empire_os.first_party_sales_interest import CommercialInterestError
from empire_os.data_brokerage_premium_enquiry import (
    DISCOVERY,SCHEMA,discovery_catalog,record_premium_discovery,
    make_private_discovery_router,
)

NOW=datetime(2026,10,18,21,0,tzinfo=timezone.utc)
ORIGIN="https://empire-ai.co.uk"

def fields(code="brokerage_agency_discovery"):
    return {
        "product_code":code,
        "business_name":"Fixture B2B Agency Ltd",
        "email":"reviewer@example.test",
        "domain":"example.test",
        "industry":"Marketing agency",
        "geography":"Leeds, UK",
        "desired_outcome":"Compare two clients' local roofing competitor pages.",
        "contact_consent":True,
        "idempotency_key":"genuine-only-in-fixture-01234",
        "website":"",
    }

def rpc_capture(*,decision="created",accepted=True):
    seen=[]
    def fake(method,path,*,payload):
        seen.append((method,path,payload))
        return (
            {"decision":decision,"prospect":{"id":"fixture-only-canonical-id"}}
            if accepted else {"decision":"unverified","prospect":{}}
        )
    return seen,fake

def test_two_unpriced_and_exact_source_catalog():
    p=discovery_catalog()
    assert set(DISCOVERY)=={"brokerage_agency_discovery","brokerage_enterprise_discovery"}
    assert p["status"]=="UNPRICED_DISCOVERY_ONLY_NOT_PUBLICLY_PUBLISHED"
    assert [x["draft_source_offer_code"] for x in p["offers"]]==[
        "agency_white_label_search","portfolio_geography_intelligence",
    ]
    assert all(x["approved_price_cents"] is None for x in p["offers"])
    assert all(x["price_approved"] is False for x in p["offers"])
    assert all(x["checkout_enabled"] is False for x in p["offers"])
    assert all(x["enquiry_enabled_in_production"] is False for x in p["offers"])

@pytest.mark.parametrize("code",tuple(DISCOVERY))
def test_buyer_initiated_exact_crm_ingest_with_no_price_or_marketing_consent(code):
    seen,request=rpc_capture()
    reply=record_premium_discovery(fields(code),request=request,now=NOW)
    assert reply["decision"]=="commercial_enquiry_recorded"
    assert reply["next_step"]=="FOUNDER_PRIVATE_SCOPE_REVIEW"
    assert reply["terms_binding"] is False
    assert reply["payment_or_revenue_verified"] is False
    assert reply["automatic_followup_sent"] is False
    assert reply["execution_authority"]=="none"
    assert len(seen)==1
    method,path,payload=seen[0]
    assert (method,path)==("POST","/rest/v1/rpc/ingest_prospect_atomic")
    assert payload["p_prospect"]["niche"]=="commercial_sales:data_brokerage_premium_discovery"
    assert payload["p_prospect"]["contacted_status"]=="not_contacted"
    assert payload["p_prospect"]["buy_signal_score"]==0
    evidence=payload["p_evidence"]
    assert evidence["schema_version"]==SCHEMA
    assert evidence["product_code"]==code
    assert evidence["contact_consent_evidence"]["newsletter_or_ongoing_marketing_consent"] is False
    assert evidence["source_rights_verified"] is False
    assert evidence["approved_price_cents"] is None
    assert evidence["automatic_followup_authorized"] is False
    assert evidence["execution_authority"]=="none"
    assert payload["p_identity_keys"][0]=="domain:example.test"
    assert payload["p_identity_keys"][1].startswith("email:")
    assert "reviewer@example.test" not in payload["p_identity_keys"][1]
    assert payload["p_ingest_key"].startswith("commercial-sales:")
    assert reply["reference"]==payload["p_ingest_key"].split(":",1)[1][:20]

def test_offer_and_idempotency_key_protect_duplicate_genuine_enquiry():
    seen,request=rpc_capture(decision="existing_ingest")
    a=record_premium_discovery(fields(),request=request,now=NOW)
    b=record_premium_discovery(fields(),request=request,now=NOW)
    assert a["reference"]==b["reference"]
    assert seen[0][2]["p_ingest_key"]==seen[1][2]["p_ingest_key"]
    changed=fields("brokerage_enterprise_discovery")
    c=record_premium_discovery(changed,request=request,now=NOW)
    assert a["reference"]!=c["reference"]

@pytest.mark.parametrize("key,value",[
    ("contact_consent",False),
    ("contact_consent",1),
    ("contact_consent","true"),
    ("website","hidden-spam"),
    ("product_code","agency_white_label_search"),
    ("product_code","portfolio_geography_intelligence"),
    ("product_code","unknown"),
    ("email","not-a-mail"),
    ("domain","not-a-company"),
    ("idempotency_key","bad"),
    ("business_name",""),
    ("desired_outcome","short"),
    ("industry",""),
])
def test_invalid_preconditions_never_touch_existing_crm(key,value):
    v=fields();v[key]=value
    seen,request=rpc_capture()
    with pytest.raises(CommercialInterestError):
        record_premium_discovery(v,request=request)
    assert seen==[]

@pytest.mark.parametrize("extra",[
    {"approved_price_cents":125000},
    {"buyer_verified":True},
    {"paid_subscription":True},
    {"source_rights_approved":True},
    {"phone_number":"+441234567890"},
])
def test_client_cannot_inject_price_terms_or_extra_attributes(extra):
    v=fields();v.update(extra)
    with pytest.raises(CommercialInterestError):
        record_premium_discovery(v,request=lambda *a,**k:pytest.fail("DB_CALLED"))

def test_buyer_receipt_only_after_canonical_ingest_confirmation():
    for decision in ("error","denied","pending",""):
        seen,request=rpc_capture(decision=decision)
        with pytest.raises(CommercialInterestError,match="not_recorded"):
            record_premium_discovery(fields(),request=request,now=NOW)
    seen,request=rpc_capture(accepted=False)
    with pytest.raises(CommercialInterestError,match="not_recorded"):
        record_premium_discovery(fields(),request=request,now=NOW)

def test_clock_must_have_timezone():
    seen,request=rpc_capture()
    with pytest.raises(CommercialInterestError):
        record_premium_discovery(fields(),request=request,
            now=datetime(2026,10,18,21,0))
    assert seen==[]

def local_api(*,allow=True):
    seen,request=rpc_capture()
    app=FastAPI()
    app.include_router(make_private_discovery_router(
        rate_limiter=lambda peer,kind:allow,
        request=request,
    ))
    return TestClient(app),seen

def test_router_not_mounted_by_default_and_requires_gateway_rate_limiter():
    assert make_private_discovery_router is not None
    with pytest.raises(ValueError,match="GATEWAY_RATE_LIMITER_REQUIRED"):
        make_private_discovery_router(rate_limiter=None)
    root=TestClient(FastAPI())
    assert root.get("/v1/brokerage/premium-discovery").status_code==404
    assert root.post("/v1/brokerage/premium-discovery").status_code==404

def test_isolated_local_api_returns_unpriced_read_only_catalog():
    client,seen=local_api()
    result=client.get("/v1/brokerage/premium-discovery")
    assert result.status_code==200
    assert result.json()["schema_version"]==SCHEMA
    assert result.json()["offers"][0]["approved_price_cents"] is None
    assert seen==[]

def test_isolated_router_consent_true_then_exact_once_rpc():
    client,seen=local_api()
    result=client.post("/v1/brokerage/premium-discovery",
        headers={"Origin":ORIGIN,"Sec-Fetch-Site":"same-origin"},
        json=fields())
    assert result.status_code==200
    assert result.json()["decision"]=="commercial_enquiry_recorded"
    assert len(seen)==1
    assert seen[0][0:2]==("POST","/rest/v1/rpc/ingest_prospect_atomic")

def test_same_origin_content_type_size_rate_limit_and_validation_before_rpc():
    client,seen=local_api()
    scenarios=(
        ({},fields(),403),
        ({"Origin":"https://evil.invalid"},fields(),403),
        ({"Origin":ORIGIN,"Sec-Fetch-Site":"cross-site"},fields(),403),
        ({"Origin":ORIGIN,"Content-Type":"text/plain"},"example",415),
        ({"Origin":ORIGIN},dict(fields(),contact_consent=False),422),
        ({"Origin":ORIGIN},dict(fields(),contact_consent="true"),422),
        ({"Origin":ORIGIN},dict(fields(),contact_consent=1),422),
        ({"Origin":ORIGIN},dict(fields(),price_guarantee=125000),422),
        ({"Origin":ORIGIN},dict(fields(),product_code="agency_white_label_search"),422),
        ({"Origin":ORIGIN},dict(fields(),desired_outcome="x"*12_001),413),
    )
    for headers,data,status in scenarios:
        if isinstance(data,str):
            res=client.post("/v1/brokerage/premium-discovery",headers=headers,content=data)
        else:
            res=client.post("/v1/brokerage/premium-discovery",headers=headers,json=data)
        assert res.status_code==status,(status,res.status_code)
    client2,seen2=local_api(allow=False)
    response=client2.post("/v1/brokerage/premium-discovery",
        headers={"Origin":ORIGIN},json=fields())
    assert response.status_code==429
    assert seen==seen2==[]

def test_database_exception_is_not_repeated_in_api_response():
    def unsafe(method,path,*,payload):
        raise RuntimeError("PRIVATE_DB_CREDENTIAL_MUST_NOT_LEAK")
    app=FastAPI()
    app.include_router(make_private_discovery_router(
        rate_limiter=lambda *a:True,request=unsafe))
    response=TestClient(app).post("/v1/brokerage/premium-discovery",
        headers={"Origin":ORIGIN},json=fields())
    assert response.status_code==503
    assert response.json()=={"detail":"premium_discovery_temporarily_unavailable"}
