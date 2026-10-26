#!/usr/bin/env python3
"""Semrush-style OWNED keyword visibility, original daily SEO observer.

Two bounded read-only calls to original Search Intelligence loopback GSC.
Writes no new DB or service; immutable receipt under existing daily SEO owner.
"""
from __future__ import annotations

import argparse
from datetime import date,datetime,timedelta,timezone
from hashlib import sha256
import fcntl
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from empire_os.search_intelligence.seo_visibility_v1 import (
    build_visibility_review, VisibilityEvidenceHeld
)

ROOT=Path("/home/ubuntu/empire_releases/seo_daily_index_status_20261026")
SOURCE="http://127.0.0.1:8771/v1/search/search-console/observations"
MAX_BODY=160_000


def _original_gsc_query_page(start:date,end:date) -> dict:
    params=urlencode({"start_date":start.isoformat(),"end_date":end.isoformat(),"limit":250})
    with urlopen(SOURCE+"?"+params,timeout=6) as response:
        if response.status!=200:
            raise VisibilityEvidenceHeld("ORIGINAL_GSC_SERVICE_UNAVAILABLE")
        raw=response.read(MAX_BODY+1)
        if len(raw)>MAX_BODY:
            raise VisibilityEvidenceHeld("OVERSIZE_ORIGINAL_GSC_EVIDENCE")
    result=json.loads(raw)
    if not isinstance(result,dict):
        raise VisibilityEvidenceHeld("ORIGINAL_GSC_SOURCE_NOT_OBJECT")
    return result


def build_run(*, as_of:date, reader=None) -> dict:
    if type(as_of) is not date or as_of>datetime.now(timezone.utc).date():
        raise VisibilityEvidenceHeld("CURRENT_OR_PRIOR_DATE_REQUIRED")
    end=as_of-timedelta(days=4)
    start=end-timedelta(days=9)
    prior_end=start-timedelta(days=1)
    prior_start=prior_end-timedelta(days=9)
    get=reader or _original_gsc_query_page
    a=get(prior_start,prior_end)
    b=get(start,end)
    packet=build_visibility_review(a,b,previous_window=(prior_start,prior_end),
        current_window=(start,end),as_of=as_of)
    packet["two_gsc_read_only_requests"]=2
    packet["original_seo_owner_reused"]=True
    return packet


def run(*,as_of:date|None=None,write:bool=False,
        root:Path=ROOT,reader=None)->dict:
    day=as_of or datetime.now(timezone.utc).date()
    if type(day) is not date:
        raise VisibilityEvidenceHeld("VALID_DATE_REQUIRED")
    target=root/f"seo-visibility-{day.isoformat()}.json"
    if write:
        if (not root.is_dir() or root.is_symlink()
            or root.stat().st_uid!=os.geteuid()
            or root.stat().st_mode&0o077):
            raise VisibilityEvidenceHeld("ORIGINAL_PRIVATE_SEO_OWNER_REQUIRED")
        if target.is_symlink():
            raise VisibilityEvidenceHeld("UNSAFE_EXISTING_VISIBILITY_RECEIPT")
        if target.is_file():
            data=json.loads(target.read_text("utf8"))
            if data.get("schema_version")!="empire.search.original_gsc_visibility_overlap.v1":
                raise VisibilityEvidenceHeld("UNTRUSTED_EXISTING_VISIBILITY_SCHEMA")
            return {"status":"EXISTING_ORIGINAL_GSC_VISIBILITY_PRESERVED",
                "receipt":str(target),"new_gsc_calls":0,"modified":False}
    report=build_run(as_of=day,reader=reader)
    if not write:
        return report
    lockfd=os.open(root/".seo-visibility.lock",
        os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(lockfd,"rb") as handle:
        fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        fd=os.open(target,os.O_EXCL|os.O_CREAT|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,"w",encoding="utf8") as out:
            json.dump(report,out,indent=2,sort_keys=True)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
    return {
        "status":"ORIGINAL_GSC_VISIBILITY_MONITOR_RECORDED",
        "receipt":str(target),
        "sha256":sha256(target.read_bytes()).hexdigest(),
        "observed_queries":report["observed_queries"],
        "commercial_relevant_queries_observed":report["commercial_relevant_queries_observed"],
        "sampled_query_page_rows":report["current_sample"]["returned_query_page_rows"],
        "paid_requests":0,"site_changed":False,"outbound_sent":False,
        "database_writes":False,"new_timer":False,
    }


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--write-daily",action="store_true")
    args=parser.parse_args()
    try:
        item=run(write=args.write_daily)
        if not args.write_daily:
            item={k:v for k,v in item.items() if k!="queries"}|{"top_queries":item["queries"][:12]}
        print(json.dumps(item,sort_keys=True))
        return 0
    except Exception as err:
        print(json.dumps({"status":"ORIGINAL_GSC_VISIBILITY_HELD",
            "reason_code":type(err).__name__,"site_changed":False,
            "outbound_sent":False,"database_writes":False}))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
