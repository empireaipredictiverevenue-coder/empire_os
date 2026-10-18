#!/usr/bin/env python3
"""Check that LIVE Founder API HTTP routes loaded the enterprise evidence guard.

Read-only localhost-only smoke test: JSON, HTML and Markdown are checked
for no-store, nosniff, and internal-unverified draft semantics. This is NOT
a customer delivery, financial audit, source rights check or fake-data
injection into the production process.
"""
from __future__ import annotations

import argparse,json,time
from urllib.error import URLError
from urllib.request import Request,urlopen

ROOT="http://127.0.0.1:8766"
ROUTE="/v1/predictive-revenue/product-workbench/enterprise-report"
PATHS={
    "json":ROUTE,
    "html":ROUTE+"/preview",
    "markdown":ROUTE+"/markdown",
}
TYPES={
    "json":"application/json",
    "html":"text/html",
    "markdown":"text/plain",
}


def _brief_startup_refusal(exc):
    """Only connection refusal from the fixed loopback address is retriable.

    A server HTTP error (including HTTP 409), timeout or malformed response
    is never retried/misrepresented as mere startup latency.
    """
    if isinstance(exc, ConnectionRefusedError):
        return True
    return (isinstance(exc, URLError)
            and isinstance(getattr(exc,"reason",None), ConnectionRefusedError))


def check_live_routes(*,opener=urlopen,sleeper=time.sleep):
    checks=[]
    for name,path in PATHS.items():
        # Only the fixed Founder loopback port is queried. The *first* route
        # may briefly refuse connections while the existing systemd unit
        # starts. Retry those refusals up to 4 attempts; all other failures
        # hold immediately and all evidence assertions remain mandatory.
        req=Request(ROOT+path,headers={"Accept":TYPES[name]})
        attempt_limit=4 if name=="json" else 1
        for attempt in range(attempt_limit):
            try:
                result=opener(req,timeout=8)
                with result as resp:
                    body=resp.read(256_000)
                    header=resp.headers
                    status=getattr(resp,"status",200)
                break
            except (OSError,ValueError,TimeoutError) as exc:
                if (attempt+1<attempt_limit
                        and _brief_startup_refusal(exc)):
                    sleeper(1)
                    continue
                checks.append({"route":name,"result":"HOLD_UNREACHABLE_OR_ERROR",
                               "connection_attempts":attempt+1})
                break
        else:
            raise AssertionError("unreachable attempt sequence")
        if len(checks) and checks[-1].get("result")=="HOLD_UNREACHABLE_OR_ERROR":
            break
        meta={
            "route":name,
            "connection_attempts":attempt+1,
            "http_status":status,
            "no_store":header.get("Cache-Control")=="no-store",
            "no_sniff":header.get("X-Content-Type-Options")=="nosniff",
            "content_type_expected":header.get("Content-Type","").startswith(TYPES[name]),
        }
        verified=False
        if status==200 and all(meta[key] for key in (
            "no_store","no_sniff","content_type_expected"
        )):
            if name=="json":
                try:
                    payload=json.loads(body)
                    verified=(
                        payload.get("schema_version")==
                        "empire.predictive_revenue.enterprise_diagnostic_report.v1"
                        and payload.get("report_disposition")==
                        "INTERNAL_DRAFT_NOT_CLIENT_DELIVERABLE"
                        and payload.get("chapter_count")==12
                        and payload.get("completeness",{}).get("findings_verified")==0
                        and payload.get("release_gate",{}).get("customer_delivery_enabled") is False
                        and payload.get("release_gate",{}).get("client_release_approved") is False
                    )
                except (ValueError,TypeError,AttributeError):
                    verified=False
            else:
                verified=(b"INTERNAL" in body.upper()
                          and b"NOT VERIFIED" in body.upper())
        meta["result"]="GUARDED_INTERNAL_DRAFT_ROUTE" if verified else "HOLD_ROUTE_GUARD_NOT_VERIFIED"
        checks.append(meta)
    ok=len(checks)==3 and all(
        c.get("result")=="GUARDED_INTERNAL_DRAFT_ROUTE" for c in checks
    )
    return {
        "status":"LIVE_REPORT_GUARDS_VERIFIED" if ok else "HOLD_LIVE_REPORT_GUARD_UNVERIFIED",
        "checked_local_only":True,
        "service_host":"127.0.0.1",
        "route_count_checked":len(checks),
        "checks":checks,
        "fabricated_customer_finding_injected_into_production":False,
        "customer_delivery_authorized":False,
        "execution_authority":"none",
    }


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--read-only",action="store_true")
    args=p.parse_args(argv)
    if not args.read_only:
        print(json.dumps({"status":"HOLD_EXPLICIT_READ_ONLY_REQUIRED"}))
        return 2
    result=check_live_routes()
    print(json.dumps(result,sort_keys=True))
    return 0 if result["status"]=="LIVE_REPORT_GUARDS_VERIFIED" else 2


if __name__=="__main__":
    raise SystemExit(main())
