#!/usr/bin/env python3
"""One-shot original SEO timer's after-review: 5 real Google indexed URLs.

Uses EXISTING loopback Search Intelligence URL Inspection reader (6-hour cache)
and EXISTING owned-site technical crawl. A separate scheduled service/timer
is NOT created. Data are privately retained by the original Ubuntu owner.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from urllib.request import urlopen

from empire_os.search_intelligence.google_index_change_watch import (
    summarize_verified_google_index,
)
from empire_os.search_intelligence.owned_url_inspection import (
    ROOFING_GUIDE_URLS,
)
from empire_os.search_intelligence.gsc_indexed_truth_review import (
    review_owned_google_index_evidence,
)

ROOT=Path("/home/ubuntu/empire_releases/seo_daily_index_status_20261026")
API="http://127.0.0.1:8771/v1/search/search-console/indexed-version/fixed"
DAY_REGEX=re.compile(r"^google-index-(\d{4}-\d{2}-\d{2})\.json$")

GUIDE_API="http://127.0.0.1:8771/v1/search/search-console/indexed-version/roofing-guides"
GUIDE_DAY_REGEX=re.compile(r"^google-roofing-guides-(\d{4}-\d{2}-\d{2})\.json$")
GUIDE_SCHEMA="empire.search.original_roofing_guide_google_index_daily.v1"

def private_dir(root: Path, *, create: bool) -> None:
    if create and not root.exists():
        root.mkdir(mode=0o700,parents=False,exist_ok=False)
    if (not root.is_dir() or root.is_symlink() or
        root.stat().st_uid != os.geteuid() or
        (root.stat().st_mode & 0o077)):
        raise PermissionError("ORIGINAL_UBUNTU_PRIVATE_EVIDENCE_DIRECTORY_REQUIRED")

def scan_previous(root:Path, today: str):
    previous=None
    for path in sorted(root.iterdir()):
        m=DAY_REGEX.fullmatch(path.name)
        if not m or m.group(1)>=today:
            continue
        if path.is_symlink() or not path.is_file():
            raise PermissionError("UNEXPECTED_PRIVATE_RECEIPT_ENTRY")
        previous=path
    if previous is not None:
        return json.loads(previous.read_text(encoding="utf-8"))
    return None

def review_daily_published_roofing_guides(
    root: Path=ROOT, *, write_daily:bool=False,
    observed:datetime|None=None
) -> dict:
    """Two previously published fixed URLs via the EXISTING cached GSC API.

    Separate private dated receipt, but same original daily SEO process.
    No Google live test/index submission, second timer, or person-level
    attribution. Missing or unavailable provider evidence stays unknown.
    """
    now=observed or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("OBSERVATION_CLOCK_MUST_HAVE_TIMEZONE")
    utc=now.astimezone(timezone.utc)
    date=utc.date().isoformat()
    if write_daily:
        private_dir(root,create=True)
    target=root/("google-roofing-guides-"+date+".json")
    if write_daily and (target.exists() or target.is_symlink()):
        if target.is_symlink() or not target.is_file():
            raise PermissionError("UNTRUSTED_ROOFING_RECEIPT")
        recorded=json.loads(target.read_text(encoding="utf-8"))
        if (recorded.get("schema_version")!=GUIDE_SCHEMA or
            recorded.get("url_scope")!=list(ROOFING_GUIDE_URLS) or
            recorded.get("mode")!="OBSERVE"):
            raise ValueError("UNTRUSTED_ROOFING_RECEIPT")
        return {"status":"ROOFING_GUIDES_DAILY_ALREADY_RECORDED",
                "source_updated":False,
                "scope_checked":2,
                "provider_requested":False,
                "changes_detected":recorded["change_count"],
                "website_changed":False,"google_indexing_submissions":0}
    previous=None
    if root.is_dir():
        private_dir(root,create=False)
        last=None
        for path in sorted(root.iterdir()):
            match=GUIDE_DAY_REGEX.fullmatch(path.name)
            if not match or match.group(1)>=date:
                continue
            if path.is_symlink() or not path.is_file():
                raise PermissionError("UNTRUSTED_PREVIOUS_ROOFING_RECEIPT")
            last=path
        if last is not None:
            previous=json.loads(last.read_text(encoding="utf-8"))
            if (previous.get("schema_version")!=GUIDE_SCHEMA or
                previous.get("url_scope")!=list(ROOFING_GUIDE_URLS) or
                previous.get("mode")!="OBSERVE" or
                previous.get("execution_authority")!="none"):
                raise ValueError("UNTRUSTED_PREVIOUS_ROOFING_RECEIPT")
    with urlopen(GUIDE_API,timeout=74) as response:
        if response.status!=200:
            raise OSError("ORIGINAL_ROOFING_GOOGLE_INDEX_READER_HELD")
        payload=json.loads(response.read(200_000))
    if (payload.get("schema_version") !=
            "empire.search.owned_roofing_guide_index_inspection.v1" or
        payload.get("status") !=
            "ROOFING_GUIDES_INDEXED_VERSION_INSPECTION_RECORDED" or
        payload.get("count") != 2 or
        payload.get("mode") != "OBSERVE" or
        payload.get("google_live_test_performed") is not False or
        payload.get("google_indexing_request_sent") is not False or
        payload.get("production_database_writes") is not False or
        payload.get("website_changed") is not False or
        payload.get("execution_authority") != "none"):
        raise ValueError("ORIGINAL_EXACT_ROOFING_GSC_EVIDENCE_REQUIRED")
    try:
        provider_at=datetime.fromisoformat(payload["observed_at"])
        if provider_at.tzinfo is None:
            raise ValueError("clock not UTC-aware")
        age=(utc-provider_at.astimezone(timezone.utc)).total_seconds()
    except (KeyError,ValueError,TypeError) as exc:
        raise ValueError("ROOFING_GSC_PROVIDER_TIMESTAMP_REQUIRED") from exc
    if not -300<=age<=8*3600:
        raise ValueError("ROOFING_GSC_RECEIPT_STALE")
    items=payload.get("items")
    if (not isinstance(items,list) or len(items)!=2 or
        [x.get("url") for x in items if isinstance(x,dict)]
            !=list(ROOFING_GUIDE_URLS)):
        raise ValueError("ONLY_TWO_PUBLISHED_ROOFING_URLS_ALLOWED")
    facts={}
    for row in items:
        url=row["url"]
        verdict=row.get("verdict")
        coverage=row.get("coverageState")
        crawled=row.get("lastCrawlTime")
        if (verdict not in ("PASS","FAIL","NEUTRAL","VERDICT_UNSPECIFIED") or
            not isinstance(coverage,str) or len(coverage)>250 or
            crawled is not None and not isinstance(crawled,str) or
            row.get("google_indexed_version_only") is not True or
            row.get("live_url_test_performed") is not False):
            raise ValueError("ROOFING_GUIDE_INDEX_STATUS_INVALID")
        facts[url]={"verdict":verdict,"coverageState":coverage,
                    "lastCrawlTime":crawled,
                    "google_reported_indexed":verdict=="PASS"}
    changes=[]
    if previous is not None:
        before=previous.get("exact_url_states")
        if (not isinstance(before,dict) or
            set(before)!=set(ROOFING_GUIDE_URLS)):
            raise ValueError("ROOFING_PREVIOUS_SCOPE_INVALID")
        for url in ROOFING_GUIDE_URLS:
            old=before[url];current=facts[url]
            if old!=current:
                changes.append({"url":url,"previous":old,"current":current,
                   "new_google_indexed_version_observed":(
                      old.get("google_reported_indexed") is not True and
                      current["google_reported_indexed"] is True)})
    result={"schema_version":GUIDE_SCHEMA,
       "status":"GOOGLE_ROOFING_GUIDE_INDEX_OBSERVATION_RECORDED",
       "mode":"OBSERVE","observed_at_utc":utc.isoformat(),
       "google_original_observed_at":payload["observed_at"],
       "provider_observation_age_seconds":int(age),
       "url_scope":list(ROOFING_GUIDE_URLS),"scope_checked":2,
       "exact_url_states":facts,"previous_watch_exists":previous is not None,
       "changes_since_previous_review":changes,"change_count":len(changes),
       "google_reported_indexed_count":sum(v["google_reported_indexed"]
                                              for v in facts.values()),
       "actual_search_clicks_verified":False,
       "human_homeowner_visits_verified":False,
       "qualified_enquiries_verified":False,
       "settled_revenue_verified":False,
       "google_live_test_performed":False,
       "google_indexing_submissions":0,
       "database_writes":False,"website_changed":False,
       "outbound_sent":False,"execution_authority":"none"}
    if write_daily:
        fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,"w",encoding="utf-8") as stream:
            json.dump(result,stream,sort_keys=True,indent=2)
            stream.write("\n");stream.flush();os.fsync(stream.fileno())
    return {"status":"GOOGLE_ROOFING_GUIDE_INDEX_DAILY_RECORDED" if write_daily
                   else "GOOGLE_ROOFING_GUIDE_INDEX_DAILY_PREVIEW",
            "scope_checked":2,
            "google_reported_indexed_count":result["google_reported_indexed_count"],
            "changes_detected":len(changes),
            "provider_observation_age_seconds":int(age),
            "source_updated":write_daily,
            "google_indexing_submissions":0,
            "website_changed":False,"new_timer_or_service":False}


def execute(root:Path=ROOT, *, write_daily:bool=False, observed:datetime|None=None):
    now=observed or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("OBSERVATION_CLOCK_MUST_HAVE_TIMEZONE")
    today=now.astimezone(timezone.utc).date().isoformat()
    if write_daily:
        private_dir(root,create=True)
        dest=root/("google-index-"+today+".json")
        if dest.exists() or dest.is_symlink():
            existing=json.loads(dest.read_text(encoding="utf-8"))
            if (existing.get("schema_version") !=
                "empire.search.google_index_daily_watch.v1"):
                raise ValueError("EXISTING_PRIVATE_EVIDENCE_NOT_TRUSTED")
            return {"status":"ORIGINAL_DAILY_INDEX_WATCH_ALREADY_RECORDED",
                    "scope_checked":existing["scope_checked"],
                    "indexed_verified":existing["indexed_verified"],
                    "unknown_to_google":existing["unknown_to_google"],
                    "source_updated":False}
    previous=scan_previous(root,today) if root.is_dir() else None
    with urlopen(API,timeout=74) as response:
        if response.status!=200:
            raise OSError("ORIGINAL_GSC_INDEXED_ENDPOINT_NOT_READY")
        raw=response.read(200_000)
    original=json.loads(raw)
    # Uses exact existing audited site source. No search engine or Google
    # re-crawler; solely checks first-party site health.
    from empire_os.search_intelligence.seo_indexing_health import audit_live_indexing
    health=audit_live_indexing()
    joined=review_owned_google_index_evidence(original,health)
    packet=summarize_verified_google_index(joined,previous,now=now)
    if write_daily:
        fd=os.open(dest,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,"w",encoding="utf-8") as stream:
            json.dump(packet,stream,sort_keys=True,indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    return {
        "status":"ORIGINAL_DAILY_GOOGLE_INDEX_REVIEW_RECORDED" if write_daily
                else "ORIGINAL_DAILY_GOOGLE_INDEX_PREVIEW_ONLY",
        "scope_checked":packet["scope_checked"],
        "indexed_verified":packet["indexed_verified"],
        "unknown_to_google":packet["unknown_to_google"],
        "changed_from_previous":packet["change_count"],
        "google_observed_at":packet["original_google_observed_at"],
        "site_critical_issues":packet["site_critical_issues"],
        "google_indexing_submissions":0,
        "database_writes":False,
        "new_timer_or_service":False,
        "outbound_sent":False,
    }

def main():
    parser=argparse.ArgumentParser()
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--review-only",action="store_true")
    group.add_argument("--write-daily",action="store_true")
    args=parser.parse_args()
    try:
        result=execute(write_daily=args.write_daily)
    except Exception as exc:
        # The current original service must not be marked failed by
        # independent provider timeout or one bad Google status. The explicit
        # UNKNOWN status (not false zero indexing) is recorded in journal.
        result={"status":"ORIGINAL_DAILY_GOOGLE_INDEX_SOURCE_UNAVAILABLE",
                "reason_code":type(exc).__name__,
                "indexed_verified":None,"unknown_to_google":None,
                "google_indexing_submissions":0,"new_timer_or_service":False}
    if (args.write_daily and result.get("status") in {
            "ORIGINAL_DAILY_GOOGLE_INDEX_REVIEW_RECORDED",
            "ORIGINAL_DAILY_INDEX_WATCH_ALREADY_RECORDED",
        }):
        # The original daily SEO service owns this sequence. Its primary
        # Google index receipt remains immutable if optional lifecycle work
        # fails; no new timer, service or database has been introduced.
        try:
            from scripts.review_original_seo_action_lifecycle_20261026 import run as seo_cycle
            result["seo_action_lifecycle"] = seo_cycle(write=True)
        except Exception as lifecycle_error:
            result["seo_action_lifecycle"] = {
                "status": "SEO_LIFECYCLE_HELD_PRIMARY_GOOGLE_WATCH_PRESERVED",
                "reason_code": type(lifecycle_error).__name__,
                "website_changed": False,
                "outbound_sent": False,
                "database_writes": False,
            }
    if (args.write_daily and result.get("status") in {
            "ORIGINAL_DAILY_GOOGLE_INDEX_REVIEW_RECORDED",
            "ORIGINAL_DAILY_INDEX_WATCH_ALREADY_RECORDED",
        }):
        # Original daily owner also owns Semrush-like query/page history.
        # Exactly two bounded original GSC loopback GETs, private immutable
        # receipt; optional failure NEVER fails Google/index/lifecycle owner.
        try:
            from scripts.review_original_gsc_visibility_v1_20261026 import run as visibility
            result["seo_keyword_visibility"] = visibility(write=True)
        except Exception as visibility_error:
            result["seo_keyword_visibility"] = {
                "status":"SEO_KEYWORD_VISIBILITY_HELD_GOOGLE_WATCH_PRESERVED",
                "reason_code":type(visibility_error).__name__,
                "site_changed":False,"outbound_sent":False,
                "database_writes":False,
            }
    if args.write_daily:
        # Same original daily observer. Separate exact two-URL immutable
        # receipt; fail-soft so no provider outage breaks legacy SEO checks.
        try:
            result["seo_published_roofing_guide_index"] = (
                review_daily_published_roofing_guides(write_daily=True)
            )
        except Exception as guide_error:
            result["seo_published_roofing_guide_index"] = {
                "status":"ROOFING_GUIDE_GOOGLE_INDEX_SOURCE_UNAVAILABLE",
                "reason_code":type(guide_error).__name__,
                "google_reported_indexed_count":None,
                "changes_detected":None,
                "website_changed":False,
                "google_indexing_submissions":0,
                "new_timer_or_service":False,
            }
    print(json.dumps(result,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
