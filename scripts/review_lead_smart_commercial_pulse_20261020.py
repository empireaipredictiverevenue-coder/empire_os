#!/usr/bin/env python3
"""Read-only, privacy-minimal Lead Smart roofing commercial pulse.

GSC impressions are discovery evidence, not proof of indexing, visitors or paid
calls. Site handoffs are dial-link permits, not connected calls. Ringba matched
rows can contain prior tests and do NOT establish payable revenue.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timedelta,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any,Callable
from urllib.parse import urlencode
from urllib.request import urlopen,Request

ROOT=Path("/srv/empire_os")
CONTROL=ROOT/"runtime/revenue/lead_smart/pilot/approved_control.json"
LEDGER=ROOT/"runtime/revenue/lead_smart/pilot/site_handoffs.json"
TRACKING=ROOT/"runtime/revenue/lead_smart/ringba/tracking_verification/latest.json"
OUT=ROOT/"runtime/revenue/lead_smart/commercial_pulse/latest.json"
GSC="http://127.0.0.1:8771/v1/search/search-console/pages"
CANONICAL="https://empire-ai.co.uk/roofing"
MAX_BYTES=200000

def read_json(path:Path)->dict[str,Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size>MAX_BYTES:
        raise RuntimeError("missing_or_oversized_"+path.name)
    value=json.loads(path.read_text())
    if not isinstance(value,dict):raise ValueError("expected_json_object")
    return value

def gsc_pages(start:str,end:str)->dict[str,Any]:
    params=urlencode({"start_date":start,"end_date":end,"limit":1000})
    req=Request(GSC+"?"+params,headers={"Accept":"application/json"})
    with urlopen(req,timeout=12) as response:
        if response.status!=200:raise RuntimeError("gsc_endpoint_non200")
        data=response.read(MAX_BYTES+1)
        if len(data)>MAX_BYTES:raise RuntimeError("gsc_oversize")
    doc=json.loads(data)
    if (not isinstance(doc,dict) or doc.get("available") is not True
            or doc.get("site_url")!="sc-domain:empire-ai.co.uk"
            or doc.get("data_state") not in ("final","partial")
            or not isinstance(doc.get("items"),list)):
        raise ValueError("gsc_unverified")
    rows=[]
    for record in doc["items"]:
        if not isinstance(record,dict):continue
        keys=record.get("keys")
        if (keys not in ([CANONICAL],[CANONICAL+"/"])
            or type(record.get("clicks")) is not int
            or type(record.get("impressions")) is not int):
            continue
        rows.append(record)
    return {"status":"PAGE_ROW_OBSERVED" if rows else "NO_REPORTED_PAGE_ROW",
            "period_start":start,"period_end":end,
            "source_state":doc["data_state"],
            "clicks":sum(x["clicks"] for x in rows),
            "impressions":sum(x["impressions"] for x in rows),
            "indexed_in_google_verified":False,
            "unique_human_visitors_verified":False}

def ringba_proof()->dict[str,Any]:
    # Existing root-owned key NEVER enters this script or its environment.
    # An authorised existing observer emits restricted aggregate evidence only.
    cmd=["sudo","-n",str(ROOT/".venv/bin/python"),"-B","-m",
         "scripts.probe_lead_smart_ringba_root_readonly"]
    try:
        result=subprocess.run(cmd,cwd=ROOT,timeout=30,capture_output=True,text=True,check=False)
        payload=json.loads(result.stdout)
        if (result.returncode!=0 or
            payload.get("schema_version")!="empire.lead_smart.ringba_privileged_one_hit.v1"
            or payload.get("account_selection_resolved") is not True):
            raise ValueError("restricted_reader_not_verified")
        matched=(payload.get("call_log_evidence") or {}).get("matching_campaign_number_call_rows")
        if type(matched) is not int or not 0<=matched<=100000:
            raise ValueError("invalid_match_count")
        return {"status":"RESTRICTED_PROVIDER_ROWS_OBSERVED",
                "matching_rows_in_returned_window":matched,
                "includes_historical_test_calls":"POSSIBLE",
                "buyer_leg_connected_verified":False,
                "payable_call_verified":False,
                "settled_revenue_verified":False,
                "provider_token_read_by_unprivileged_process":False}
    except (OSError,ValueError,subprocess.SubprocessError,json.JSONDecodeError):
        return {"status":"PROVIDER_AGGREGATE_UNAVAILABLE",
                "matching_rows_in_returned_window":None,
                "buyer_leg_connected_verified":False,
                "payable_call_verified":False,
                "settled_revenue_verified":False,
                "provider_token_read_by_unprivileged_process":False}

def pulse(*, now:datetime|None=None,provider_reader:Callable=ringba_proof,
          gsc_reader:Callable=gsc_pages,control_path:Path=CONTROL,
          ledger_path:Path=LEDGER,tracking_path:Path=TRACKING)->dict[str,Any]:
    clock=now or datetime.now(timezone.utc)
    if clock.tzinfo is None:raise ValueError("timezone_aware_clock_required")
    clock=clock.astimezone(timezone.utc)
    config=read_json(control_path)
    if (config.get("campaign_id")!="CA8278ed3f26e9495b881fe3833174d007"
            or config.get("tracking_number")!="+18883579305"):
        raise RuntimeError("unexpected_campaign")
    ledger=read_json(ledger_path) if ledger_path.exists() else None
    total=ledger.get("site_handoffs") if ledger else 0
    if type(total) is not int or total<0:raise ValueError("invalid_handoff_ledger")
    localday=clock.astimezone(__import__("zoneinfo").ZoneInfo("America/Chicago")).date().isoformat()
    currentday=ledger.get("daily_site_handoffs",0) if ledger and ledger.get("local_day")==localday else 0
    if type(currentday) is not int or currentday<0:raise ValueError("invalid_daily_handoffs")
    tracking=read_json(tracking_path)
    today=clock.date()
    start=(today-timedelta(days=14)).isoformat()
    end=(today-timedelta(days=1)).isoformat()
    try:gsc=gsc_reader(start,end)
    except (OSError,ValueError,RuntimeError):
        gsc={"status":"GSC_UNAVAILABLE","clicks":None,"impressions":None,
             "indexed_in_google_verified":False,
             "unique_human_visitors_verified":False,
             "period_start":start,"period_end":end}
    return {
        "schema_version":"empire.lead_smart.commercial_pulse.v1",
        "observed_at_utc":clock.isoformat(),
        "campaign_id":config["campaign_id"],
        "buyer":"Lead Smart",
        "site_route":"/roofing",
        "campaign_mode":config.get("mode"),
        "site_handoff_switch_enabled":config.get("enabled") is True,
        "campaign_expires_at":config.get("ends_at"),
        "daily_site_handoff_limit":config.get("max_daily_site_handoffs"),
        "total_site_handoff_limit":config.get("max_site_handoffs"),
        "site_handoffs_recorded":total,
        "site_handoffs_today":currentday,
        "handoff_metric":"consent-acknowledged dial-link admissions; NOT connected calls",
        "google_search_console":gsc,
        "ringba":provider_reader(),
        "tracking_assignment_observed_at":tracking.get("verified_at"),
        "actual_connected_homeowner_calls_verified":False,
        "qualified_billable_calls_verified":False,
        "settled_revenue_verified":False,
        "gross_profit_verified":False,
        "no_real_revenue_inferred_from_tracking":True,
        "raw_call_identifiers_persisted":False,
        "caller_personal_data_persisted":False,
    }

def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--write-latest",action="store_true")
    args=parser.parse_args()
    data=pulse()
    if args.write_latest:
        import os,tempfile
        OUT.parent.mkdir(parents=True,exist_ok=True)
        fd,name=tempfile.mkstemp(prefix=".commercial-pulse-",dir=OUT.parent)
        try:
            with os.fdopen(fd,"w") as f:
                json.dump(data,f,indent=2,sort_keys=True)
                f.write("\n")
                f.flush();os.fsync(f.fileno())
            os.chmod(name,0o644)
            os.replace(name,OUT)
        finally:
            if os.path.exists(name):os.unlink(name)
    print(json.dumps(data,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
