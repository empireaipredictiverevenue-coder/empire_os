"""Two-hop public-to-private Data Brokerage enquiry, all effects mocked.

These tests do not connect to production EmpireDB and never change the
gateway/frontend production apps. The positive calls below use fixture RPC.
"""
from __future__ import annotations

import json
from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
import pytest

from empire_os.data_brokerage_premium_enquiry import (
    DISCOVERY,make_private_discovery_router
)
from empire_os.data_brokerage_premium_gateway_adapter import (
    PUBLIC_PATH,PRIVATE_PATH,PRIVATE_LOOPBACK_URL,
    safe_public_discovery_catalog,make_reviewed_public_premium_gateway_router,
    _safe_confirmed_receipt,forward_to_private_checkout
)

ORIGIN="https://empire-ai.co.uk"

def data(code="brokerage_agency_discovery"):
    return {
        "product_code":code,"business_name":"Fixture Partner Ltd",
        "email":"person@example.test","domain":"example.test",
        "industry":"Search agency","geography":"Yorkshire UK",
        "desired_outcome":"We want independent original local market competitor analysis.",
        "contact_consent":True,"idempotency_key":"test-fixture-premium-00001",
        "website":"",
    }

def app_pair(*,approved=True,allow=True,backend_mutator=None,db_throws=False):
    calls=[]
    private=FastAPI()
    def fake_rpc(method,path,*,payload):
        calls.append((method,path,payload))
        if db_throws:
            raise RuntimeError("VERY_PRIVATE_DATABASE_CREDENTIAL")
        return {"decision":"created","prospect":{"id":"fixture-prospect-uuid"}}
    private.include_router(make_private_discovery_router(
        rate_limiter=lambda peer,kind:True,
        request=fake_rpc,
    ))
    async def forward(raw):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=private),
            base_url="http://127.0.0.1:8098",
        ) as client:
            r=await client.post(
                PRIVATE_PATH,content=raw,
                headers={"Origin":ORIGIN,"Sec-Fetch-Site":"same-origin",
                         "Content-Type":"application/json"}
            )
        response=r.json()
        if backend_mutator is not None:
            response=backend_mutator(response)
        return r.status_code,response
    public=FastAPI()
    if approved:
        public.include_router(make_reviewed_public_premium_gateway_router(
            rate_limiter=lambda peer,kind:allow,
            forward=forward,
            founder_release_approved=True,
            existing_private_checkout_route_verified=True,
            astra_frontend_review_complete=True,
        ))
    return TestClient(public),calls

def post(client,payload=None,headers=None):
    return client.post(
        PUBLIC_PATH,
        headers=({"Origin":ORIGIN,"Sec-Fetch-Site":"same-origin"} if headers is None else headers),
        json=(data() if payload is None else payload),
    )

def test_routers_are_not_mounted_into_real_apps_by_import():
    import empire_os.public_gateway as gateway
    import empire_os.self_serve_checkout_api as checkout
    assert all(getattr(route,"path",None)!=PUBLIC_PATH for route in gateway.app.routes)
    assert all(getattr(route,"path",None)!=PRIVATE_PATH for route in checkout.app.routes)

@pytest.mark.parametrize("flag",[
    "founder_release_approved",
    "existing_private_checkout_route_verified",
    "astra_frontend_review_complete",
])
def test_private_public_mount_requires_independent_release_flag(flag):
    switches={
        "founder_release_approved":True,
        "existing_private_checkout_route_verified":True,
        "astra_frontend_review_complete":True,
    }
    switches[flag]=False
    with pytest.raises(ValueError,match="RELEASE_AUTHORITY_HOLD"):
        make_reviewed_public_premium_gateway_router(
            rate_limiter=lambda *args:True,
            forward=lambda raw:None,**switches
        )
    never=TestClient(FastAPI())
    assert never.get(PUBLIC_PATH).status_code==404
    assert never.post(PUBLIC_PATH).status_code==404

def test_no_rate_limiter_or_forwarder_is_safe_hold():
    for limit,forward in ((None,lambda _:None),(lambda *a:True,None)):
        with pytest.raises(ValueError,match="RELEASE_AUTHORITY_HOLD"):
            make_reviewed_public_premium_gateway_router(
                rate_limiter=limit,forward=forward,
                founder_release_approved=True,
                existing_private_checkout_route_verified=True,
                astra_frontend_review_complete=True,
            )

def test_public_get_contains_no_private_hypothesis_prices_or_skus():
    client,calls=app_pair()
    response=client.get(PUBLIC_PATH)
    assert response.status_code==200
    assert response.headers["cache-control"]=="no-store"
    body=response.json()
    assert body["count"]==2
    assert body["binding_terms_ready"] is False
    assert body["payment_authorized"] is False
    assert {x["product_code"] for x in body["offers"]}==set(DISCOVERY)
    assert all(x["price_state"]=="DISCUSS_CUSTOM_SCOPE" for x in body["offers"])
    raw=json.dumps(body)
    assert "1250" not in raw and "4000" not in raw
    assert "agency_white_label_search" not in raw
    assert "portfolio_geography_intelligence" not in raw
    assert calls==[]

@pytest.mark.parametrize("code",list(DISCOVERY))
def test_realistic_two_hop_fixtured_buyer_consent_flows_only_to_atomic_crm(code):
    client,calls=app_pair()
    reply=post(client,data(code))
    assert reply.status_code==200,reply.text
    assert reply.headers["cache-control"]=="no-store"
    body=reply.json()
    assert body["decision"]=="commercial_enquiry_recorded"
    assert body["product_code"]==code
    assert len(body["reference"])==20
    assert body["binding_terms_ready"] is False
    assert body["payment_action"] is False
    assert body["revenue_recognized"] is False
    assert "email" not in json.dumps(body)
    assert len(calls)==1
    assert calls[0][0:2]==("POST","/rest/v1/rpc/ingest_prospect_atomic")
    evidence=calls[0][2]["p_evidence"]
    assert evidence["approved_price_cents"] is None
    assert evidence["contact_consent_evidence"]["newsletter_or_ongoing_marketing_consent"] is False
    assert evidence["automatic_followup_authorized"] is False
    assert evidence["checkout_authorized"] is False
    assert calls[0][2]["p_prospect"]["contacted_status"]=="not_contacted"

@pytest.mark.parametrize("headers,payload,status",[
    ({},data(),403),
    ({"Origin":"https://evil.example"},data(),403),
    ({"Origin":ORIGIN,"Sec-Fetch-Site":"cross-site"},data(),403),
    ({"Origin":ORIGIN,"Content-Type":"text/plain"},"hello",415),
    ({"Origin":ORIGIN},dict(data(),contact_consent=False),422),
    ({"Origin":ORIGIN},dict(data(),contact_consent=1),422),
    ({"Origin":ORIGIN},dict(data(),contact_consent="true"),422),
    ({"Origin":ORIGIN},dict(data(),website="trap"),422),
    ({"Origin":ORIGIN},dict(data(),product_code="agency_white_label_search"),422),
    ({"Origin":ORIGIN},dict(data(),price=1250),422),
])
def test_public_security_before_forward(headers,payload,status):
    client,calls=app_pair()
    if isinstance(payload,str):
        result=client.post(PUBLIC_PATH,content=payload,headers=headers)
    else:
        result=post(client,payload,headers)
    assert result.status_code==status,(status,result.status_code,result.text)
    assert result.headers["cache-control"]=="no-store"
    assert calls==[]

def test_rate_limit_blocks_no_rpc_calls():
    client,calls=app_pair(allow=False)
    r=post(client)
    assert r.status_code==429
    assert calls==[]

def test_oversized_body_content_length_is_rejected_before_forward():
    client,calls=app_pair()
    over=dict(data(),desired_outcome="X"*13000)
    result=post(client,over)
    assert result.status_code==413
    assert calls==[]

def test_only_confirmed_safe_receipt_can_reach_browser():
    for mutate in (
        lambda x:dict(x,execution_authority="money"),
        lambda x:dict(x,buyer_identity_qualified=True),
        lambda x:dict(x,payment_or_revenue_verified=True),
        lambda x:dict(x,terms_binding=True),
        lambda x:dict(x,reference="INVALID"),
    ):
        client,calls=app_pair(backend_mutator=mutate)
        r=post(client)
        assert r.status_code==503
        assert r.json()=={"error":"premium_discovery_confirmation_unavailable"}
        assert len(calls)==1

def test_db_exceptions_redacted_across_both_hops():
    client,calls=app_pair(db_throws=True)
    response=post(client)
    assert response.status_code==503
    assert "VERY_PRIVATE" not in response.text
    assert response.json()=={"error":"premium_discovery_unavailable"}
    assert len(calls)==1

def test_bounded_fixed_loopback_target_and_no_auto_publication():
    assert PRIVATE_LOOPBACK_URL=="http://127.0.0.1:8098"+PRIVATE_PATH
    assert PUBLIC_PATH.startswith("/v1/checkout/")
    assert "example" not in PRIVATE_LOOPBACK_URL
    assert "127.0.0.1" in PRIVATE_LOOPBACK_URL
