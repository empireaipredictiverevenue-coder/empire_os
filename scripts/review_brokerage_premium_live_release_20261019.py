#!/usr/bin/env python3
"""Founder read-only truth for the narrow premium Data Brokerage launch.

This reads *only* two fixed loopback public GETs plus exact local
site-asset checksum and working-tree status. Never submits a buyer form.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Callable,Any
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.error import HTTPError,URLError

ROOT=Path("/srv/empire_os")
CURRENT_HTML=ROOT/"apps/empire-public-site/out/commercial.html"
STAGED_HTML=Path(
    "/home/ubuntu/empire_worktrees/brokerage_premium_activation_20261018/"
    "apps/empire-public-site/out/commercial.html"
)
PRIVATE_URL="http://127.0.0.1:8098/v1/brokerage/premium-discovery"
PUBLIC_URL="http://127.0.0.1/v1/checkout/brokerage/premium-discovery"
SCHEMA="empire.data_brokerage.actual_live_release_readonly.v1"
PREMIUM_CODES={"brokerage_agency_discovery","brokerage_enterprise_discovery"}
STATUS_PRIVATE="UNPRICED_DISCOVERY_ONLY_NOT_PUBLICLY_PUBLISHED"
STATUS_PUBLIC="UNPRICED_DISCOVERY_CHOICES_NONBINDING"

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        return None

def get_json(url:str)->tuple[int,dict[str,Any]|None]:
    if url not in {PRIVATE_URL,PUBLIC_URL}:
        raise ValueError("NON_ALLOWLISTED_URL")
    req=Request(url,headers={"Accept":"application/json"},
                method="GET")
    try:
        with build_opener(NoRedirect).open(req,timeout=4) as res:
            raw=res.read(16000+1)
            if len(raw)>16000:raise ValueError("OVERSIZED_RESPONSE")
            if "application/json" not in res.headers.get("content-type",""):
                raise ValueError("INVALID_CONTENT_TYPE")
            data=json.loads(raw)
            if type(data) is not dict:raise ValueError("INVALID_RESPONSE_SHAPE")
            return res.status,data
    except HTTPError as err:
        return err.code,None
    except (URLError,OSError,ValueError,UnicodeError,json.JSONDecodeError):
        return 0,None

def same_site_build(
    current:Path=CURRENT_HTML,staged:Path=STAGED_HTML,
)->tuple[bool,bool]:
    if not current.is_file() or not staged.is_file():
        return False,False
    for path in (current,staged):
        if path.stat().st_size>2_000_000:raise ValueError("HTML_TOO_LARGE")
    return True,sha256(current.read_bytes()).digest()==sha256(staged.read_bytes()).digest()

def shared_source_pending(root:Path=ROOT)->bool:
    proc=subprocess.run(
        ["git","status","--porcelain","--",
         "empire_os/public_gateway.py",
         "empire_os/self_serve_checkout_api.py"],
        cwd=root,capture_output=True,text=True,timeout=6,
    )
    if proc.returncode!=0: raise ValueError("GIT_BASE_UNAVAILABLE")
    return bool(proc.stdout.strip())

def evaluate(
    private:tuple[int,dict[str,Any]|None],
    public:tuple[int,dict[str,Any]|None],
    *,
    static_exists:bool,
    static_identical:bool,
    concurrent_shared_edits:bool,
)->dict[str,Any]:
    ph,pv=private
    gh,gv=public
    private_ok=(
        ph==200 and type(pv) is dict
        and pv.get("status")==STATUS_PRIVATE
        and type(pv.get("offers")) is list
        and len(pv["offers"])==2
        and {x.get("product_code") for x in pv["offers"] if type(x) is dict}==PREMIUM_CODES
        and all(x.get("approved_price_cents") is None
                and x.get("checkout_enabled") is False
                and x.get("enquiry_enabled_in_production") is False
                for x in pv["offers"])
    )
    public_ok=(
        gh==200 and type(gv) is dict
        and gv.get("status")==STATUS_PUBLIC
        and gv.get("count")==2
        and type(gv.get("offers")) is list
        and {x.get("product_code") for x in gv["offers"] if type(x) is dict}==PREMIUM_CODES
        and all(x.get("price_state")=="DISCUSS_CUSTOM_SCOPE"
                and x.get("checkout_enabled") is False
                and x.get("public_approved_price_available") is False
                for x in gv["offers"])
        and gv.get("payment_authorized") is False
        and gv.get("binding_terms_ready") is False
    )
    blockers=[]
    if not private_ok:
        blockers.append("PRIVATE_ROUTE_NOT_VERIFIED_LIVE")
    if not public_ok:
        blockers.append("PUBLIC_GATEWAY_ROUTE_NOT_VERIFIED_LIVE")
    if not static_exists:
        blockers.append("SITE_ARTIFACT_COMPARISON_UNAVAILABLE")
    elif not static_identical:
        blockers.append("STAGED_SITE_BUILD_DIFFERS_FROM_CURRENT_LIVE_HTML")
    if concurrent_shared_edits:
        blockers.append("OTHER_AGENT_SHARED_GATEWAY_OR_CHECKOUT_EDITS_PENDING")
    return {
        "schema_version":SCHEMA,
        "mode":"READ_ONLY",
        "private_get_http_status":ph,
        "public_get_http_status":gh,
        "private_route_responds_with_two_unpriced_choices":private_ok,
        "public_route_responds_with_two_unpriced_choices":public_ok,
        "site_comparison_available":static_exists,
        "staged_site_identical_to_live_html":static_identical if static_exists else False,
        "shared_gateway_checkout_edits_pending":concurrent_shared_edits,
        "blockers":blockers,
        "status":(
            "BROKERAGE_PREMIUM_TWO_API_GET_ROUTES_LIVE_FRONTEND_UNVERIFIED"
            if private_ok and public_ok
            else "BROKERAGE_PREMIUM_API_RELEASE_INCOMPLETE"
        ),
        "website_customer_form_published_and_working_proven":False,
        "actual_buyer_enquiry_verified":False,
        "end_to_end_founder_crm_delivery_verified":False,
        "customer_accepted_subscription":False,
        "payment_settlement_verified":False,
        "realised_revenue_verified":False,
        "site_mutation":False,"database_writes":False,
        "outbound_sent":False,"paid_api_calls":0,
        "execution_authority":"NONE",
    }

def inspect(
    *, getter:Callable[[str],tuple[int,dict[str,Any]|None]]=get_json,
    files:Callable[[],tuple[bool,bool]]=same_site_build,
    edits:Callable[[],bool]=shared_source_pending,
)->dict[str,Any]:
    try:
        comparison_exists,identical=files()
        evidence=evaluate(
            getter(PRIVATE_URL),getter(PUBLIC_URL),
            static_exists=comparison_exists,static_identical=identical,
            concurrent_shared_edits=edits(),
        )
        return evidence
    except Exception:
        return {
            "schema_version":SCHEMA,"mode":"READ_ONLY",
            "status":"HOLD_PREMIUM_RELEASE_EVIDENCE_UNAVAILABLE",
            "database_writes":False,"outbound_sent":False,
            "site_mutation":False,"realised_revenue_verified":False,
        }

def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",action="store_true")
    args=parser.parse_args(argv)
    if not args.read_only:
        print(json.dumps({"status":"HOLD_EXPLICIT_READ_ONLY_REQUIRED"}))
        return 2
    result=inspect()
    print(json.dumps(result,sort_keys=True))
    return 0 if result["status"]=="BROKERAGE_PREMIUM_TWO_API_GET_ROUTES_LIVE_FRONTEND_UNVERIFIED" else 2

if __name__=="__main__":
    raise SystemExit(main())
