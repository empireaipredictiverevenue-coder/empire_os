#!/usr/bin/env python3
"""Run one explicitly approved Brave API request without result persistence.

No Brave URL/title/snippet list is output or written anywhere. This is
provider health and a transient search use only, not persisted discovery or
Buyer Scout ingestion. Existing canonical Scout keeps BRAVE_API_KEY unset.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from empire_os.a2a_brave_transient_budget_v1 import (
    MAX_PER_DAY, MAX_PER_MONTH, PRESETS, reserve_single_request,
)

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime" / "a2a_commercial_signal_mining" / "brave_meter"
ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
APPROVAL = "FOUNDER_APPROVED_BRAVE_TRANSIENT_SINGLE_QUERY_20261020"


def execute_once(market: str, *, root: Path = RUNTIME, get=None,
                 key: str | None = None) -> dict[str,Any]:
    if market not in PRESETS:
        raise ValueError("UNAPPROVED_MARKET_QUERY")
    api_key = key if key is not None else os.environ.get("BRAVE_API_KEY", "")
    if (not isinstance(api_key,str) or len(api_key.strip()) < 12
            or api_key.strip()=="YOUR_ACTUAL_BRAVE_KEY"
            or any(ch.isspace() for ch in api_key)):
        return {"state":"BRAVE_KEY_NOT_CONFIGURED", "provider_requests_attempted":0,
                "search_result_records_stored":0,"buyer_scout_writes":0}
    # Reserve before the request, including failed attempts; no retries.
    reservation = reserve_single_request(root)
    if not reservation["request_permitted"]:
        return {
            "state":"LOCAL_BRAVE_REQUEST_CAP_REACHED",
            "provider_requests_attempted":0,
            "daily_requests_used":reservation["daily_requests"],
            "monthly_requests_used":reservation["monthly_requests"],
            "search_result_records_stored":0,
            "buyer_scout_writes":0,
        }
    if get is None:
        import requests
        get = requests.get
    status = None
    result_count = 0
    state = "NETWORK_FAILURE"
    try:
        r = get(
            ENDPOINT,
            params={"q":PRESETS[market],"count":3},
            headers={
                "X-Subscription-Token": api_key,
                "Accept":"application/json",
                "User-Agent":"EmpireAI-Ephemeral-Research/1.0",
            },
            timeout=(3,10),allow_redirects=False,
        )
        status = r.status_code
        if status == 200:
            content = r.content
            if len(content)>200_000:
                state="UNTRUSTED_OVERSIZED_BRAVE_RESPONSE"
            else:
                body = r.json()
                records = body.get("web",{}).get("results",[]) if isinstance(body,dict) else None
                if isinstance(records,list):
                    # Transient counts only; no URLs, titles, snippets, contacts or models.
                    result_count = min(len(records),3)
                    state="BRAVE_WEB_RESULTS_USED_TRANSIENTLY"
                else:
                    state="UNTRUSTED_BRAVE_RESULT_SHAPE"
        elif status == 429:
            state="BRAVE_QUOTA_OR_RATE_LIMITED"
        elif status in (401,403,422):
            state="BRAVE_ACCOUNT_OR_REQUEST_REJECTED"
        else:
            state="BRAVE_NON_SUCCESS_HTTP"
    except (Exception,) as err:
        # Never serialize the exception text: it may contain request secrets.
        state="BRAVE_REQUEST_FAILED"
    return {
        "schema_version":"empire.a2a.brave_transient_operation.v1",
        "state":state,"market_scope":market,
        "http_status":status,
        "provider_requests_attempted":1,
        "transient_result_count_seen":result_count,
        "daily_requests_used":reservation["daily_requests"],
        "monthly_requests_used":reservation["monthly_requests"],
        "monthly_limit":MAX_PER_MONTH,"daily_limit":MAX_PER_DAY,
        "search_result_records_stored":0,
        "search_results_emitted":False,
        "derived_company_records_stored":0,
        "buyer_scout_writes":0,"outbound_messages":0,
        "source_results_used_to_train_model":False,
    }


def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--market",choices=sorted(PRESETS),required=True)
    actions=p.add_mutually_exclusive_group(required=True)
    actions.add_argument("--dry-run",action="store_true")
    actions.add_argument("--execute-one-request",action="store_true")
    p.add_argument("--approval",default="")
    args=p.parse_args()
    if args.execute_one_request:
        if args.approval != APPROVAL:
            raise ValueError("EXPLICIT_SINGLE_BRAVE_QUERY_APPROVAL_REQUIRED")
        result=execute_once(args.market)
    else:
        result=reserve_single_request(RUNTIME,dry_run=True)
        result.update({"state":"DRY_RUN_NO_BRAVE_PROVIDER_REQUEST",
                       "market_scope":args.market,
                       "provider_requests_attempted":0,
                       "search_result_records_stored":0})
    print(json.dumps(result,sort_keys=True))
    return 0 if result.get("provider_requests_attempted")==0 or result.get("http_status")==200 else 3


if __name__=="__main__":
    raise SystemExit(main())
