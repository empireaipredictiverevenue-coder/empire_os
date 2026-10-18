#!/usr/bin/env python3
"""One GET-only public commercial offer check joined to private brokerage drafts.

No contact forms are submitted. Only the exact allowlisted public catalogue
is downloaded (max 100k); no PII, private sources, or DNS-derived URLs.
"""
from __future__ import annotations
import argparse
import json
from urllib.request import Request,HTTPRedirectHandler,build_opener
from typing import Any,Callable

from empire_os.data_brokerage_public_interest_bridge import (
    SCHEMA,review_visibility
)
from scripts.review_data_brokerage_sales_activation_20261018 import (
    review as read_private_sales
)

EXACT_URL="https://empire-ai.co.uk/v1/checkout/commercial/offers"
MAX_BYTES=100_000

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,new_url):
        return None

def _http_catalog()->dict[str,Any]:
    req=Request(EXACT_URL,headers={
        "Accept":"application/json",
        "User-Agent":"EmpireOS-BrokerageReadOnlyEnquiryCatalog/1",
    },method="GET")
    with build_opener(_NoRedirect).open(req,timeout=8) as response:
        if response.status!=200:
            raise ValueError("PUBLIC_CATALOG_HTTP_STATUS")
        if "application/json" not in response.headers.get("content-type","").lower():
            raise ValueError("PUBLIC_CATALOG_CONTENT_TYPE")
        content=response.read(MAX_BYTES+1)
        if len(content)>MAX_BYTES:
            raise ValueError("PUBLIC_CATALOG_OVERSIZED")
    return json.loads(content)

def inspect(*,public_fetch:Callable[[],dict[str,Any]]=_http_catalog,
            private_fetch:Callable[...,dict[str,Any]]=read_private_sales)->dict[str,Any]:
    try:
        private=private_fetch(show_packages=True)
        public=public_fetch()
        return review_visibility(private,public)
    except (OSError,ValueError,TypeError,KeyError,UnicodeError):
        return {
            "schema_version":SCHEMA,
            "status":"HOLD_PUBLIC_ENQUIRY_SOURCE_OR_PRIVATE_AUTHORITY_UNVERIFIED",
            "mode":"OBSERVE","public_page_post_was_not_executed":True,
            "website_mutation":False,"customer_record_exported":False,
            "email_sent":False,"payment_activated":False,"database_writes":False,
            "execution_authority":"NONE",
        }

def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",action="store_true")
    args=parser.parse_args(argv)
    if not args.read_only:
        print(json.dumps({"status":"HOLD_EXPLICIT_GET_ONLY_APPROVAL_REQUIRED"}))
        return 2
    result=inspect()
    print(json.dumps(result,sort_keys=True,allow_nan=False))
    return 0 if result["status"]=="ONE_PUBLIC_ENTRY_TWO_PRIVATE_RECURRING_DRAFTS" else 2

if __name__=="__main__":
    raise SystemExit(main())
