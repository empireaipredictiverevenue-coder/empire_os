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
import re
from pathlib import Path
import subprocess
import sys
from typing import Any,Callable
from urllib.parse import urlencode
from urllib.request import urlopen,Request

from empire_os.lead_smart_operating_hours import fifty_state_hours_overlap

ROOT=Path("/srv/empire_os")
CONTROL=ROOT/"runtime/revenue/lead_smart/pilot/approved_control.json"
LEDGER=ROOT/"runtime/revenue/lead_smart/pilot/site_handoffs.json"
TRACKING=ROOT/"runtime/revenue/lead_smart/ringba/tracking_verification/latest.json"
OUT=ROOT/"runtime/revenue/lead_smart/commercial_pulse/latest.json"
GSC="http://127.0.0.1:8771/v1/search/search-console/pages"
CANONICAL="https://empire-ai.co.uk/roofing"
# Both source-reviewed guides were first published at the original website
# owner release on 11 Nov 2026; metrics before this date are prepublication.
GUIDE_PUBLICATION_DATE="2026-11-11"
GUIDES=(
    "https://empire-ai.co.uk/roofing/installation-checklist",
    "https://empire-ai.co.uk/roofing/replacement-vs-repair",
)
MAX_BYTES=200000

MAX_ZIP_JOURNAL_BYTES=512 * 1024
ZIP_JOURNAL_UNIT="empire-public-gateway.service"
ZIP_JOURNAL_PATTERN=re.compile(
    r'"POST /roofing/coverage-check HTTP/1\.[01]" ([1-5][0-9]{2})\b'
)


def zip_check_http_request_observation(
    *, now:datetime, runner:Callable=subprocess.run,
)->dict[str,Any]:
    """Operational gateway request counts only, never real visitor conversion.

    The source is the EXISTING public gateway journal. No cookies, addresses,
    property ZIPs, bodies, identifiers or raw log lines are returned/stored.
    Operator tests and bots cannot be excluded, so these are HTTP REQUESTS
    and must never be represented as unique homeowner sessions or enquiries.
    """
    base={
        "schema_version":"empire.lead_smart.zip_http_operational_observation.v1",
        "source":"EXISTING_PUBLIC_GATEWAY_JOURNAL",
        "source_unit":ZIP_JOURNAL_UNIT,
        "window_hours":24,
        "http_post_requests":None,
        "http_200_guidance_responses":None,
        "http_4xx_responses":None,
        "http_5xx_responses":None,
        "http_other_responses":None,
        "raw_addresses_or_property_zips_exported":False,
        "additional_analytics_collector_enabled":False,
        "includes_operator_tests_or_bots_possible":True,
        "unique_homeowner_visitors_verified":False,
        "source_attribution_verified":False,
        "eligibility_or_contact_consent_verified":False,
        "buyer_accepted_calls_verified":False,
        "settled_revenue_verified":False,
    }
    if not isinstance(now,datetime) or now.tzinfo is None:
        return {**base,"status":"HTTP_JOURNAL_CLOCK_UNVERIFIED"}
    clock=now.astimezone(timezone.utc)
    if clock > datetime.now(timezone.utc)+timedelta(minutes=2):
        return {**base,"status":"HTTP_JOURNAL_FUTURE_CLOCK_HELD"}
    start=clock-timedelta(hours=24)
    command=[
        "journalctl","--unit="+ZIP_JOURNAL_UNIT,
        "--since="+start.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "--until="+clock.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "--no-pager","--output=cat",
        "--grep=POST /roofing/coverage-check",
    ]
    try:
        result=runner(command,capture_output=True,text=True,
                      timeout=12,check=False)
        output=result.stdout
        if (result.returncode!=0 or type(output) is not str
                or len(output.encode("utf-8"))>MAX_ZIP_JOURNAL_BYTES):
            return {**base,"status":"HTTP_JOURNAL_UNAVAILABLE_OR_UNBOUNDED"}
        codes=[]
        for row in output.splitlines():
            if not row.strip():
                continue
            matches=list(ZIP_JOURNAL_PATTERN.finditer(row))
            # One exact normalized Uvicorn request log per journal row.
            if len(matches)!=1:
                return {**base,"status":"HTTP_JOURNAL_LOG_FORMAT_UNVERIFIED"}
            codes.append(int(matches[0].group(1)))
        return {
            **base,
            "status":"HTTP_REQUEST_COUNTS_ONLY_NOT_VISITORS",
            "http_post_requests":len(codes),
            "http_200_guidance_responses":sum(n==200 for n in codes),
            "http_4xx_responses":sum(400<=n<500 for n in codes),
            "http_5xx_responses":sum(500<=n<600 for n in codes),
            "http_other_responses":sum(not (
                n==200 or 400<=n<600) for n in codes),
        }
    except (OSError,ValueError,UnicodeError,subprocess.SubprocessError):
        return {**base,"status":"HTTP_JOURNAL_UNAVAILABLE_OR_UNBOUNDED"}


ROOFING_PAGE_PATTERN=re.compile(
    r'"GET /roofing(?:\?[^" ]{1,2048})? HTTP/1\.[01]" ([1-5][0-9]{2})\b'
)
ROOFING_GUIDE_PATTERN=re.compile(
    r'"GET /roofing/(?:installation-checklist|replacement-vs-repair)'
    r'(?:\?[^" ]{1,2048})? HTTP/1\.[01]" ([1-5][0-9]{2})\b'
)


def roofing_content_http_request_observation(
    *, now:datetime, runner:Callable=subprocess.run,
)->dict[str,Any]:
    """Count only existing gateway GET requests; not visitor sessions.

    This is deliberately independent of the analytics consent/collection
    pipeline. No IP, referrer, request query or request log line is returned.
    CDN cache hits are not observed; bots and operator tests are included.
    Never derive a page-to-ZIP conversion rate from these HTTP totals.
    """
    base={
        "schema_version":"empire.lead_smart.roofing_http_content_observation.v1",
        "status":"HTTP_JOURNAL_UNAVAILABLE_OR_UNBOUNDED",
        "source":"EXISTING_PUBLIC_GATEWAY_JOURNAL",
        "source_unit":ZIP_JOURNAL_UNIT,
        "window_hours":24,
        "landing_get_requests":None,
        "guide_get_requests":None,
        "http_200_responses":None,
        "http_4xx_responses":None,
        "http_5xx_responses":None,
        "raw_addresses_queries_or_referrers_exported":False,
        "includes_operator_tests_or_bots_possible":True,
        "cdn_cache_hits_unobserved":True,
        "unique_homeowner_visitors_verified":False,
        "source_attribution_verified":False,
        "consented_sessions_verified":False,
        "landing_to_zip_conversion_verified":False,
        "buyer_accepted_calls_verified":False,
        "settled_revenue_verified":False,
        "additional_analytics_collector_enabled":False,
    }
    if not isinstance(now,datetime) or now.tzinfo is None:
        return {**base,"status":"HTTP_JOURNAL_CLOCK_UNVERIFIED"}
    clock=now.astimezone(timezone.utc)
    if clock>datetime.now(timezone.utc)+timedelta(minutes=2):
        return {**base,"status":"HTTP_JOURNAL_FUTURE_CLOCK_HELD"}
    start=clock-timedelta(hours=24)
    command=[
        "journalctl","--unit="+ZIP_JOURNAL_UNIT,
        "--since="+start.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "--until="+clock.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "--no-pager","--output=cat",
        r"--grep=GET /roofing( HTTP|\?|/(installation-checklist|replacement-vs-repair))",
    ]
    try:
        result=runner(command,capture_output=True,text=True,
                      timeout=12,check=False)
        output=result.stdout
        if (result.returncode!=0 or type(output) is not str
                or len(output.encode("utf-8"))>MAX_ZIP_JOURNAL_BYTES):
            return base
        types=[]
        codes=[]
        for row in output.splitlines():
            if not row.strip():
                continue
            landing=ROOFING_PAGE_PATTERN.findall(row)
            guide=ROOFING_GUIDE_PATTERN.findall(row)
            if len(landing)+len(guide)!=1:
                return {**base,"status":"HTTP_JOURNAL_LOG_FORMAT_UNVERIFIED"}
            types.append("landing" if landing else "guide")
            codes.append(int((landing or guide)[0]))
        return {
            **base,
            "status":"HTTP_REQUEST_COUNTS_ONLY_NOT_VISITORS",
            "landing_get_requests":types.count("landing"),
            "guide_get_requests":types.count("guide"),
            "http_200_responses":sum(code==200 for code in codes),
            "http_4xx_responses":sum(400<=code<500 for code in codes),
            "http_5xx_responses":sum(500<=code<600 for code in codes),
        }
    except (OSError,ValueError,UnicodeError,subprocess.SubprocessError):
        return base


def buyer_hours_and_campaign_window(*, now:datetime,
                                    control:dict[str,Any]) -> dict[str,Any]:
    """Current conservative clock overlap, never proof of an accepting buyer.

    Actual Ringba routing, caller-origin verification, recording governance,
    revised buyer terms and founder release all remain separate authorities.
    The read-only pulse MUST NOT imply that an open clock enables a call.
    """
    if now.tzinfo is None:
        raise ValueError("timezone_aware_clock_required")
    utc=now.astimezone(timezone.utc)
    overlap=fifty_state_hours_overlap(now=utc)
    state="INVALID_WINDOW_HELD"
    try:
        start=datetime.fromisoformat(str(control.get("starts_at","")))
        end=datetime.fromisoformat(str(control.get("ends_at","")))
        if (start.tzinfo is not None and end.tzinfo is not None
                and start < end):
            start=start.astimezone(timezone.utc)
            end=end.astimezone(timezone.utc)
            state=("NOT_STARTED" if utc < start else
                   "EXPIRED" if utc >= end else "IN_WINDOW")
    except (TypeError,ValueError,OverflowError):
        pass
    return {
        "schema_version":"empire.lead_smart.hours_and_campaign_observation.v1",
        "mode":"READ_ONLY_NEVER_CALL_AUTHORITY",
        "evaluated_at_utc":utc.isoformat(),
        "source_refs":["gmail:1a12229d9d3ffe75",
                       "gmail:1a15ea2dfa8c46b1"],
        "reported_weekday_local_hours":"08:00-18:00",
        "reported_weekend_local_hours":"10:00-16:00",
        "reported_timezone_policy":"CALLER_LOCAL_NOT_UNIVERSAL_CHICAGO",
        "all_fifty_state_reported_clocks_in_window":
            overlap["all_reported_windows_open"],
        "campaign_window_state":state,
        "campaign_config_switch_enabled":control.get("enabled") is True,
        "specific_callers_timezone_verified":False,
        "current_buyer_capacity_verified":False,
        "current_buyer_offer_terms_verified":False,
        "buyer_route_and_ani_verified":False,
        "independent_recording_compliance_verified":False,
        "actual_live_call_authorized":False,
        "fresh_founder_campaign_window_authorized":False,
        "consumer_call_traffic_enabled_by_observation":False,
    }


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
    guides=[]
    for url in GUIDES:
        matched=[]
        for record in doc["items"]:
            if not isinstance(record,dict):
                continue
            if record.get("keys") not in ([url],[url+"/"]):
                continue
            clicks=record.get("clicks")
            impressions=record.get("impressions")
            if (type(clicks) is not int or type(impressions) is not int
                    or clicks<0 or impressions<0):
                raise ValueError("gsc_guide_row_invalid")
            matched.append(record)
        guides.append({
            "url":url,
            "status":"PAGE_ROW_OBSERVED" if matched else "NO_REPORTED_PAGE_ROW",
            # Missing GSC row is UNKNOWN, not proven zero traffic/indexation.
            "clicks":sum(x["clicks"] for x in matched) if matched else None,
            "impressions":sum(x["impressions"] for x in matched) if matched else None,
            "indexed_in_google_verified":False,
            "unique_human_visitors_verified":False,
        })
    return {"status":"PAGE_ROW_OBSERVED" if rows else "NO_REPORTED_PAGE_ROW",
            "period_start":start,"period_end":end,
            "source_state":doc["data_state"],
            "clicks":sum(x["clicks"] for x in rows),
            "impressions":sum(x["impressions"] for x in rows),
            "indexed_in_google_verified":False,
            "unique_human_visitors_verified":False,
            "guide_observations":{
                "schema_version":"empire.lead_smart.gsc_guide_page_observations.v1",
                "publication_date_utc":GUIDE_PUBLICATION_DATE,
                "gsc_period_end_precedes_guide_publication":
                    end<GUIDE_PUBLICATION_DATE,
                "source_state":doc["data_state"],
                "status":"PAGE_DIMENSION_GUIDES_REVIEWED",
                "pages":guides,
                "google_indexation_verified":False,
                "consented_enquiries_verified":False,
                "real_sales_verified":False,
            }}

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
          gsc_reader:Callable=gsc_pages,
          zip_request_reader:Callable=zip_check_http_request_observation,
          content_request_reader:Callable=roofing_content_http_request_observation,
          control_path:Path=CONTROL,
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
        "buyer_hours_and_campaign_window":
            buyer_hours_and_campaign_window(now=clock,control=config),
        "daily_site_handoff_limit":config.get("max_daily_site_handoffs"),
        "total_site_handoff_limit":config.get("max_site_handoffs"),
        "site_handoffs_recorded":total,
        "site_handoffs_today":currentday,
        "handoff_metric":"consent-acknowledged dial-link admissions; NOT connected calls",
        "google_search_console":gsc,
        "google_search_console_guides":gsc.get("guide_observations",{
            "schema_version":"empire.lead_smart.gsc_guide_page_observations.v1",
            "status":"NO_VERIFIED_GUIDE_PAGE_EVIDENCE",
            "publication_date_utc":GUIDE_PUBLICATION_DATE,
            "pages":[{"url":url,"status":"EVIDENCE_UNAVAILABLE",
                      "clicks":None,"impressions":None,
                      "indexed_in_google_verified":False,
                      "unique_human_visitors_verified":False}
                     for url in GUIDES],
            "google_indexation_verified":False,
            "consented_enquiries_verified":False,
            "real_sales_verified":False,
        }),
        "zip_check_http_operational_requests":zip_request_reader(now=clock),
        "roofing_content_http_operational_requests":content_request_reader(now=clock),
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
