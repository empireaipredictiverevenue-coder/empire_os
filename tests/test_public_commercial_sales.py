"""Existing public gateway reuses narrow first-party commercial enquiry intake."""
from __future__ import annotations

import json
from pathlib import Path
from fastapi.testclient import TestClient

import empire_os.public_gateway as gateway

CLIENT = TestClient(gateway.app)
ORIGIN = "https://empire-ai.co.uk"


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.content = json.dumps(payload).encode()


class FakeHttpClient:
    seen = []
    async def __aenter__(self): return self
    async def __aexit__(self, *args): return None
    def __init__(self, **kwargs):
        assert kwargs.get("timeout") in (8.0, 20.0)
    async def get(self, url):
        self.seen.append(("GET",url,None))
        assert url == "http://127.0.0.1:8098/v1/commercial/offers"
        return FakeResponse(200,{"status":"FOUNDER_LED_ENQUIRY_AVAILABLE","count":6,"offers":[]})
    async def post(self,url,*,content,headers):
        assert url == "http://127.0.0.1:8098/v1/commercial/interests"
        assert headers["Content-Type"] == "application/json"
        body=json.loads(content)
        self.seen.append(("POST",url,body))
        return FakeResponse(200,{
            "decision":"commercial_enquiry_recorded",
            "reference":"safe-test-ref",
            "execution_authority":"none","payment_action":False,
        })


def fixture_http(monkeypatch):
    FakeHttpClient.seen=[]
    monkeypatch.setattr(gateway.httpx,"AsyncClient",FakeHttpClient)
    monkeypatch.setattr(gateway.FIRST_PARTY_INTAKE_LIMITER,"allow",lambda peer,kind:True)


def test_commercial_catalog_proxy_is_readonly(monkeypatch):
    fixture_http(monkeypatch)
    response=CLIENT.get("/v1/checkout/commercial/offers")
    assert response.status_code==200
    assert response.json()["count"]==6
    assert response.headers["cache-control"]=="no-store"
    assert FakeHttpClient.seen==[
        ("GET","http://127.0.0.1:8098/v1/commercial/offers",None)
    ]


def test_commercial_enquiry_respects_same_origin_consent_and_private_gateway(monkeypatch):
    fixture_http(monkeypatch)
    result=CLIENT.post("/v1/checkout/commercial/interests",
        headers={"Origin":ORIGIN,"Sec-Fetch-Site":"same-origin"},
        json={
            "product_code":"consultancy_opportunity_assessment",
            "contact_consent":True,
            "business_name":"Example Ltd",
            "email":"buyer@example.test",
            "domain":"example.test",
        })
    assert result.status_code==200
    assert result.json()["decision"]=="commercial_enquiry_recorded"
    assert result.json()["execution_authority"]=="none"
    assert result.headers["cache-control"]=="no-store"
    assert len(FakeHttpClient.seen)==1
    assert FakeHttpClient.seen[0][2]["contact_consent"] is True


def test_cross_origin_rejected_before_downstream_call(monkeypatch):
    fixture_http(monkeypatch)
    for headers in (
        {"Origin":"https://attacker.invalid"},
        {},
        {"Origin":ORIGIN,"Sec-Fetch-Site":"cross-site"},
    ):
        result=CLIENT.post("/v1/checkout/commercial/interests",headers=headers,json={})
        assert result.status_code==403
        assert result.json()["error"]=="same_origin_required"
    assert FakeHttpClient.seen==[]


def test_wrong_content_type_rejected_before_downstream_call(monkeypatch):
    fixture_http(monkeypatch)
    response=CLIENT.post("/v1/checkout/commercial/interests",
        headers={"Origin":ORIGIN,"Content-Type":"text/plain"},
        content="bad")
    assert response.status_code==415
    assert FakeHttpClient.seen==[]


def test_oversized_enquiry_payload_rejected_before_proxy(monkeypatch):
    fixture_http(monkeypatch)
    response=CLIENT.post("/v1/checkout/commercial/interests",
        headers={"Origin":ORIGIN},
        json={"oversized":"x"*13000})
    assert response.status_code==413
    assert FakeHttpClient.seen==[]


def test_rate_limit_rejected_without_forwarding(monkeypatch):
    fixture_http(monkeypatch)
    monkeypatch.setattr(gateway.FIRST_PARTY_INTAKE_LIMITER,"allow",lambda peer,kind:False)
    response=CLIENT.post("/v1/checkout/commercial/interests",
        headers={"Origin":ORIGIN},json={})
    assert response.status_code==429
    assert FakeHttpClient.seen==[]


def test_commercial_static_route_is_explicitly_allowlisted(tmp_path,monkeypatch):
    assert gateway._site_html_path("../commercial",tmp_path) is None
    page=tmp_path/"commercial.html"
    page.write_text("<html><title>Empire AI Commercial</title>Commercial enquiries</html>")
    assert gateway._site_html_path("commercial",tmp_path)==page
    assert "https://empire-ai.co.uk/commercial" in gateway._public_site_urls(tmp_path)
    monkeypatch.setattr(gateway,"SITE_OUT",tmp_path)
    response=CLIENT.get("/commercial")
    assert response.status_code==200
    assert "Commercial enquiries" in response.text
    assert response.headers["x-frame-options"]=="DENY"


def test_missing_export_does_not_fake_live_sales_page(tmp_path,monkeypatch):
    monkeypatch.setattr(gateway,"SITE_OUT",tmp_path)
    response=CLIENT.get("/commercial")
    assert response.status_code==404



def test_obsolete_commercial_paths_redirect_to_single_consent_based_sales_journey():
    for route in ("/contact","/consultancy","/digital-avatar","/sales"):
        result=CLIENT.get(route,follow_redirects=False)
        assert result.status_code==308
        assert result.headers["location"]=="/commercial"
        assert "empire-ai.co.uk" not in result.headers["location"]
