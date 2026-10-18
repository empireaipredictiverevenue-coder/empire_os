"""Actual three FastAPI enterprise-report routes must gate the same evidence.

The router is other-agent work, intentionally not committed by this release.
Tests exercise its locally mounted current implementation in the canonical
EmpireOS checkout.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime,timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi import HTTPException

from empire_os.enterprise_report_http_guard import (
    guarded_enterprise_http_response,EVIDENCE_HOLD_DETAIL,
)
from empire_os.enterprise_report_claim_guard import (
    validate_enterprise_report_before_render,
)


@pytest.fixture()
def valid_packet():
    # Real existing report builder; no invented values or source.
    from empire_os.predictive_revenue_enterprise_report import build_enterprise_diagnostic_report
    from pathlib import Path
    return build_enterprise_diagnostic_report(Path("/srv/empire_os"))


@pytest.mark.parametrize("format,type_head",[
    ("json","application/json"),
    ("html","text/html"),
    ("markdown","text/plain"),
])
def test_http_guard_accepts_real_internal_draft_but_never_releases(
    valid_packet, format, type_head,
):
    outcome=guarded_enterprise_http_response(valid_packet,format=format)
    assert outcome.status_code==200
    assert outcome.media_type.startswith(type_head)
    assert outcome.headers["cache-control"]=="no-store"
    assert outcome.headers["x-content-type-options"]=="nosniff"
    assert outcome.body
    assert valid_packet["release_gate"]["customer_delivery_enabled"] is False
    if format=="json":
        import json
        obj=json.loads(outcome.body)
        assert obj["completeness"]["findings_verified"]==0
        assert obj["release_gate"]["customer_delivery_enabled"] is False
    else:
        assert b"INTERNAL" in outcome.body.upper()


@pytest.mark.parametrize("tamper,value",[
    ("findings_verified",42),
    ("claims_approved_for_customer_report",1),
])
@pytest.mark.parametrize("format",["json","html","markdown"])
def test_http_guard_blocks_forged_verification_before_any_response(
    valid_packet,tamper,value,format,
):
    wrong=deepcopy(valid_packet)
    wrong["completeness"][tamper]=value
    with pytest.raises(HTTPException) as error:
        guarded_enterprise_http_response(wrong,format=format)
    assert error.value.status_code==409
    assert error.value.detail==EVIDENCE_HOLD_DETAIL
    assert valid_packet["completeness"]["findings_verified"]==0


def test_json_guard_preserves_original_and_denies_source_escalation(valid_packet):
    forged=deepcopy(valid_packet)
    forged["source_traceability"]["original_customer_source_verified"]=True
    with pytest.raises(HTTPException) as error:
        guarded_enterprise_http_response(forged,format="json")
    assert error.value.status_code==409


def test_http_guard_rejects_unknown_format_and_invalid_raw_object():
    for obj,fmt in ((None,"json"),({"x":4},"html"),({}, "csv")):
        with pytest.raises(HTTPException) as error:
            guarded_enterprise_http_response(obj,format=fmt)
        assert error.value.status_code==409
        assert error.value.detail["customer_delivery_authorized"] is False


def _client_with_payload(monkeypatch, packet):
    """Mount the exact already-existing founder report APIRouter."""
    import empire_os.predictive_revenue_demo_api as live
    monkeypatch.setattr(live,"build_enterprise_diagnostic_report",lambda root: deepcopy(packet))
    app=FastAPI(openapi_url=None)
    app.include_router(live.create_predictive_revenue_demo_router())
    return TestClient(app,raise_server_exceptions=True)


@pytest.mark.parametrize("path_suffix,media",[
    ("","application/json"),
    ("/preview","text/html"),
    ("/markdown","text/plain"),
])
def test_three_real_router_paths_enforce_evidence_gate(
    monkeypatch,valid_packet,path_suffix,media,
):
    client=_client_with_payload(monkeypatch,valid_packet)
    base="/v1/predictive-revenue/product-workbench/enterprise-report"
    response=client.get(base+path_suffix)
    assert response.status_code==200
    assert response.headers["content-type"].startswith(media)
    assert response.headers["cache-control"]=="no-store"
    assert response.headers["x-content-type-options"]=="nosniff"
    assert "INTERNAL" in response.text.upper()


@pytest.mark.parametrize("path_suffix",["","/preview","/markdown"])
@pytest.mark.parametrize("edit",["verified_count","finance","approved"])
def test_three_real_router_paths_never_render_or_json_publish_false_claim(
    monkeypatch,valid_packet,path_suffix,edit,
):
    wrong=deepcopy(valid_packet)
    if edit=="verified_count":
        wrong["completeness"]["findings_verified"]=42
    elif edit=="finance":
        wrong["executive_summary"]["observed_client_revenue_cents"]=9999999
    elif edit=="approved":
        wrong["release_gate"]["client_release_approved"]=True
    client=_client_with_payload(monkeypatch,wrong)
    base="/v1/predictive-revenue/product-workbench/enterprise-report"
    response=client.get(base+path_suffix)
    assert response.status_code==409
    assert "42 verified" not in response.text
    assert "9999999" not in response.text
    assert response.json()["detail"]==EVIDENCE_HOLD_DETAIL
    assert response.json()["detail"]["customer_delivery_authorized"] is False



def test_live_route_verification_requires_three_guarded_replies():
    from empire_os.predictive_revenue_enterprise_report import (
        build_enterprise_diagnostic_report,
    )
    from empire_os.enterprise_report_http_guard import guarded_enterprise_http_response
    from scripts.verify_enterprise_report_route_enforcement_readonly import (
        check_live_routes,
    )
    from pathlib import Path

    packet=build_enterprise_diagnostic_report(Path("/srv/empire_os"))
    resp={
        "json":guarded_enterprise_http_response(packet,format="json"),
        "html":guarded_enterprise_http_response(packet,format="html"),
        "markdown":guarded_enterprise_http_response(packet,format="markdown"),
    }

    class Reply:
        def __init__(self,live):
            self.live=live
            self.status=live.status_code
            self.headers=live.headers
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def read(self,limit):return self.live.body[:limit]

    calls=[]
    def get(request,timeout):
        assert timeout==8
        if request.full_url.endswith("/preview"):
            route="html"
        elif request.full_url.endswith("/markdown"):
            route="markdown"
        else:route="json"
        calls.append(route)
        return Reply(resp[route])

    actual=check_live_routes(opener=get)
    assert actual["status"]=="LIVE_REPORT_GUARDS_VERIFIED"
    assert calls==["json","html","markdown"]
    assert actual["customer_delivery_authorized"] is False

    class UnguardedReply(Reply):
        @property
        def headers(self):
            return {"Content-Type":"application/json"}
        @headers.setter
        def headers(self,x):pass

    def old_server(request,timeout):
        return UnguardedReply(resp["json"])
    denied=check_live_routes(opener=old_server)
    assert denied["status"]=="HOLD_LIVE_REPORT_GUARD_UNVERIFIED"



def test_live_checker_recovers_only_brief_initial_connection_refusal():
    from pathlib import Path
    from empire_os.predictive_revenue_enterprise_report import build_enterprise_diagnostic_report
    from scripts.verify_enterprise_report_route_enforcement_readonly import check_live_routes
    packet=build_enterprise_diagnostic_report(Path("/srv/empire_os"))
    responses={
        "json":guarded_enterprise_http_response(packet,format="json"),
        "html":guarded_enterprise_http_response(packet,format="html"),
        "markdown":guarded_enterprise_http_response(packet,format="markdown"),
    }
    class Reply:
        def __init__(self,x):
            self.status=x.status_code;self.headers=x.headers;self.body=x.body
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def read(self,limit):return self.body[:limit]
    called=[];slept=[]
    def opener(request,timeout):
        assert timeout==8
        url=request.full_url
        path=("html" if url.endswith("/preview") else
              "markdown" if url.endswith("/markdown") else "json")
        called.append(path)
        if len(called)<=2:
            raise ConnectionRefusedError(111,"service starting")
        return Reply(responses[path])
    proof=check_live_routes(opener=opener,sleeper=lambda n:slept.append(n))
    assert proof["status"]=="LIVE_REPORT_GUARDS_VERIFIED"
    assert called==["json","json","json","html","markdown"]
    assert slept==[1,1]
    assert proof["checks"][0]["connection_attempts"]==3
    assert proof["customer_delivery_authorized"] is False


def test_live_checker_stops_after_four_refusals_with_hold():
    from scripts.verify_enterprise_report_route_enforcement_readonly import check_live_routes
    calls=[];sleeps=[]
    def refused(request,timeout):
        calls.append(request.full_url)
        raise ConnectionRefusedError(111,"startup never finished")
    proof=check_live_routes(opener=refused,sleeper=lambda n:sleeps.append(n))
    assert proof["status"]=="HOLD_LIVE_REPORT_GUARD_UNVERIFIED"
    assert proof["route_count_checked"]==1
    assert proof["checks"][0]["connection_attempts"]==4
    assert len(calls)==4 and len(sleeps)==3


def test_live_checker_does_not_retry_http_409_or_timeout():
    from urllib.error import HTTPError
    from scripts.verify_enterprise_report_route_enforcement_readonly import check_live_routes
    for error in (HTTPError("http://127.0.0.1:8766",409,"held",{},None),
                  TimeoutError("slow API")):
        calls=[];sleeps=[]
        def failed(request,timeout):
            calls.append(request.full_url);raise error
        proof=check_live_routes(opener=failed,sleeper=lambda n:sleeps.append(n))
        assert proof["status"]=="HOLD_LIVE_REPORT_GUARD_UNVERIFIED"
        assert proof["checks"][0]["connection_attempts"]==1
        assert len(calls)==1 and sleeps==[]
