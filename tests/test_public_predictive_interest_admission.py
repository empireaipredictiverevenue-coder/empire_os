"""Predictive Revenue public POST admission must match commercial enquiry gates."""
import json

from fastapi.testclient import TestClient

import empire_os.public_gateway as gateway

CLIENT=TestClient(gateway.app)
PATH="/v1/checkout/predictive-revenue/interests"
ORIGIN="https://empire-ai.co.uk"


class Provider:
    seen=[]
    def __init__(self,**kwargs):
        assert kwargs.get("timeout")==20.0
    async def __aenter__(self):return self
    async def __aexit__(self,*args):return None
    async def post(self,url,*,content,headers):
        self.seen.append((url,content,headers))
        assert url=="http://127.0.0.1:8098/v1/predictive-revenue/interests"
        assert headers=={"Content-Type":"application/json"}
        return type("Response",(),{
            "content":b'{"decision":"deployment_interest_recorded","actual_revenue":false}',
            "status_code":200,"headers":{"content-type":"application/json"}
        })()


def setup(monkeypatch,allow=True):
    Provider.seen=[]
    monkeypatch.setattr(gateway.httpx,"AsyncClient",Provider)
    seen=[]
    def check(peer,kind):
        seen.append((peer,kind))
        return allow
    monkeypatch.setattr(gateway.FIRST_PARTY_INTAKE_LIMITER,"allow",check)
    return seen


def test_existing_legitimate_browser_request_still_reaches_only_internal_intake(monkeypatch):
    calls=setup(monkeypatch)
    response=CLIENT.post(PATH,headers={
        "Origin":ORIGIN,"Sec-Fetch-Site":"same-origin",
    },json={"product_code":"predictive_revenue_diagnostic", "contact_consent": True})
    assert response.status_code==200
    assert response.json()["decision"]=="deployment_interest_recorded"
    assert response.headers["cache-control"]=="no-store"
    assert len(Provider.seen)==1
    assert len(calls)==1 and calls[0][1]=="enquiry"


def test_cross_site_or_missing_origin_never_reaches_intake(monkeypatch):
    calls=setup(monkeypatch)
    for headers in (
        {},{"Origin":"https://evil.example"},
        {"Origin":ORIGIN,"Sec-Fetch-Site":"cross-site"},
        {"Origin":ORIGIN,"Sec-Fetch-Site":"same-site"},
    ):
        response=CLIENT.post(PATH,headers=headers,json={"hello":"world"})
        assert response.status_code==403
        assert response.json()["error"]=="same_origin_required"
        assert response.headers["cache-control"]=="no-store"
    assert calls==[]
    assert Provider.seen==[]


def test_bad_content_type_rejected_before_origin_and_provider(monkeypatch):
    calls=setup(monkeypatch)
    response=CLIENT.post(PATH,content="X"*10,
        headers={"Content-Type":"text/plain"})
    assert response.status_code==415
    assert response.json()["error"]=="application_json_required"
    assert calls==[] and Provider.seen==[]


def test_large_payload_denied_locally_and_no_pii_leaked(monkeypatch):
    calls=setup(monkeypatch)
    response=CLIENT.post(PATH,
        headers={"Origin":ORIGIN},
        json={"desired_outcome":"secret_buyer_info"*1000})
    assert response.status_code==413
    assert response.json()=={"error":"checkout_payload_too_large"}
    assert response.headers["cache-control"]=="no-store"
    assert len(calls)==1 and Provider.seen==[]
    assert "secret_buyer_info" not in response.text


def test_rate_limit_does_not_forward_request(monkeypatch):
    calls=setup(monkeypatch,allow=False)
    response=CLIENT.post(PATH,
        headers={"Origin":ORIGIN},json={"a":1})
    assert response.status_code==429
    assert response.json()["error"]=="rate_limited"
    assert len(calls)==1 and Provider.seen==[]


def test_no_origin_or_plaintext_does_not_touch_checkout(monkeypatch):
    calls=setup(monkeypatch)
    response=CLIENT.post(PATH,content='{"anything":true}',
        headers={"Content-Type":"application/json"})
    assert response.status_code==403
    assert len(calls)==0 and Provider.seen==[]
