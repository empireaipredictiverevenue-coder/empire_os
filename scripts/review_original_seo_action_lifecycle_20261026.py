#!/usr/bin/env python3
"""Daily SEO eyes/brain/hands review in the EXISTING organic SEO owner.

Input: original immutable daily Google index + weekly SEO growth receipts.
Execution: at most a bounded set of GET-only health checks on exact owned URLs.
Output: private immutable daily lifecycle snapshot for the existing Founder UI.
No new service, API writer, SEO publisher, DB schema, or outbound.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import fcntl

from empire_os.search_intelligence.seo_action_lifecycle_20261026 import (
    build_seo_action_lifecycle, _path, SEOActionHeld
)

ROOT = Path("/home/ubuntu/empire_releases/seo_daily_index_status_20261026")
WEEKLY = Path("/home/ubuntu/empire_releases/seo_weekly_gsc_two_page_20261022")
RELEASE = Path("/home/ubuntu/empire_releases/seo_aeo_governed_three_cta_20261026_v2/activation_result.json")
MAX_GETS = 8
MAX_BYTES = 200_000


def _trusted_json(path: Path, max_bytes: int = 250_000) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
        raise SEOActionHeld("ORIGINAL_SEO_EVIDENCE_FILE_UNTRUSTED")
    result = json.loads(path.read_text("utf8"))
    if not isinstance(result, dict):
        raise SEOActionHeld("ORIGINAL_SEO_EVIDENCE_NOT_OBJECT")
    return result


def _latest_weekly() -> Path:
    if WEEKLY.is_symlink() or not WEEKLY.is_dir():
        raise SEOActionHeld("ORIGINAL_WEEKLY_SEO_OWNER_UNAVAILABLE")
    files = sorted(WEEKLY.glob("weekly_seo_growth_actions_????-??-??.json"))
    if not files:
        raise SEOActionHeld("ORIGINAL_WEEKLY_ACTION_RECEIPT_MISSING")
    return files[-1]


def _read_only_page_check(url: str) -> dict:
    # Only bounded owned routes, no host, scheme, credentials or user parameters.
    route = _path(url)
    if route == "/":
        raise SEOActionHeld("ROOT_PAGE_NOT_ELIGIBLE_FOR_AUTOMATED_ACTION_TEST")
    request = Request("https://empire-ai.co.uk" + route,
                      headers={"User-Agent":"EmpireOS-SEO-Audit/1.0"},
                      method="GET")
    try:
        with urlopen(request, timeout=6) as response:
            target = urlsplit(response.geturl())
            if target.scheme != "https" or target.netloc != "empire-ai.co.uk":
                raise SEOActionHeld("UNTRUSTED_SEO_REDIRECT_DESTINATION")
            payload = response.read(MAX_BYTES + 1)
            if len(payload) > MAX_BYTES:
                raise SEOActionHeld("UNBOUNDED_OWNED_SITE_HTML")
            status = response.status
            content = response.headers.get("content-type", "")
            robots_header = response.headers.get("x-robots-tag", "")
    except (OSError, TimeoutError, ValueError, SEOActionHeld) as err:
        return {"status": "HELD_OR_UNAVAILABLE", "reason_code": type(err).__name__,
                "http_status": None, "self_canonical": None, "indexable": None}
    from html.parser import HTMLParser
    class Head(HTMLParser):
        def __init__(self):
            super().__init__()
            self.canonical = []
            self.robots = []
        def handle_starttag(self,tag,attrs):
            a = dict(attrs)
            if tag == "link" and a.get("rel") == "canonical":
                self.canonical.append(a.get("href"))
            if tag == "meta" and a.get("name") == "robots":
                self.robots.append(a.get("content",""))
    parsed=Head()
    parsed.feed(payload.decode("utf8","replace"))
    canonical="https://empire-ai.co.uk"+route
    return {
        "status": "TESTED_READ_ONLY_NO_MUTATION",
        "http_status": status,
        "self_canonical": parsed.canonical == [canonical],
        "indexable": (not any("noindex" in x.lower() for x in parsed.robots)
                      and "noindex" not in robots_header.lower()),
        "html_content_type": "text/html" in content.lower(),
        "observed_source": "live_first_party_https_GET",
        "body_sha256": sha256(payload).hexdigest(),
        "site_changed": False,
    }


def build_run(*, observed: datetime | None=None, get=None) -> dict:
    now=observed or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise SEOActionHeld("AWARE_CLOCK_REQUIRED")
    day=now.astimezone(timezone.utc).date().isoformat()
    daily=_trusted_json(ROOT / f"google-index-{day}.json")
    weekly=_trusted_json(_latest_weekly())
    release=_trusted_json(RELEASE)
    from scripts.review_live_organic_buyer_journey_20261024 import review
    buyer=review()
    result=build_seo_action_lifecycle(
        weekly,daily,buyer_journey=buyer,aeo_release=release,observed_at=now
    )
    getter=get or _read_only_page_check
    attempts=0
    for item in result["actions"]:
        if attempts >= MAX_GETS:
            break
        if item["state"] != "staged":
            continue
        methods=item["stage"]["allowed_automatic_checks"]
        if not methods:
            continue
        attempts+=1
        outcome=getter(item["url"])
        item["technical_test"]=outcome
        if (outcome.get("status") == "TESTED_READ_ONLY_NO_MUTATION"
            and outcome.get("http_status")==200
            and outcome.get("self_canonical") is True
            and outcome.get("html_content_type") is True
            and outcome.get("indexable") is True):
            item["state"]="tested"
            item["state_path"]=["detected","prioritised","staged","tested"]
            item["next_action"]="REVIEW_OWNER_CONTENT_OR_GOOGLE_INDEX_EVIDENCE_BEFORE_PUBLICATION"
        elif outcome.get("status") == "TESTED_READ_ONLY_NO_MUTATION":
            item["next_action"]="INVESTIGATE_FAILED_LIVE_TECHNICAL_CHECK"
    result["state_counts"]={name:sum(i["state"]==name for i in result["actions"])
                            for name in result["lifecycle_states"]}
    result["read_only_technical_tests_executed"]=attempts
    result["unresolved_actions"]=sum(i["state"]!="verified" for i in result["actions"])
    result["private_source_files"]={
        "daily_google_index": f"google-index-{day}.json",
        "weekly_actions": _latest_weekly().name,
        "original_aeo_release": RELEASE.name,
    }
    return result


def run(*, observed: datetime | None=None, write: bool=False, root: Path=ROOT,
        get=None) -> dict:
    now = observed or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise SEOActionHeld("AWARE_CLOCK_REQUIRED")
    day = now.astimezone(timezone.utc).date().isoformat()
    target = root / f"seo-actions-{day}.json"
    if write:
        if (root.is_symlink() or not root.is_dir()
            or root.stat().st_uid!=os.geteuid()
            or root.stat().st_mode & 0o077):
            raise SEOActionHeld("EXISTING_PRIVATE_SEO_OWNER_DIRECTORY_REQUIRED")
        if target.exists() or target.is_symlink():
            prior = _trusted_json(target)
            if prior.get("schema_version") != "empire.search.seo_action_lifecycle.v1":
                raise SEOActionHeld("UNTRUSTED_EXISTING_SEO_LIFECYCLE_RECEIPT")
            # No redundant GSC / AEO reads, site GETs or external lookups.
            return {"status":"EXISTING_SEO_LIFECYCLE_RECEIPT_PRESERVED",
                    "receipt":str(target),"modified":False,
                    "new_live_checks":0}
    packet=build_run(observed=now,get=get)
    if not write:
        return packet
    lockfd=os.open(root/".seo-actions.lock",
                   os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(lockfd,"rb") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if target.exists() or target.is_symlink():
            prior=_trusted_json(target)
            if prior.get("schema_version") != packet["schema_version"]:
                raise SEOActionHeld("UNTRUSTED_EXISTING_SEO_LIFECYCLE_RECEIPT")
            return {"status":"EXISTING_SEO_LIFECYCLE_RECEIPT_PRESERVED",
                    "receipt":str(target),"modified":False}
        fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        try:
            with os.fdopen(fd,"w",encoding="utf8") as out:
                json.dump(packet,out,sort_keys=True,indent=2)
                out.write("\n")
                out.flush()
                os.fsync(out.fileno())
        except Exception:
            target.unlink(missing_ok=True)
            raise
    return {"status":"ORIGINAL_DAILY_SEO_LIFECYCLE_RECORDED",
            "receipt":str(target),"sha256":sha256(target.read_bytes()).hexdigest(),
            "actions":packet["original_action_count"],
            "verified_or_resolved":packet["resolved_existing_owner_actions"],
            "tests":packet["read_only_technical_tests_executed"],
            "database_writes":False,"new_scheduler":False,
            "outbound_sent":False,"publisher_changed":False}


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--write-daily",action="store_true")
    args=p.parse_args()
    try:
        packet=run(write=args.write_daily)
        if not args.write_daily:
            packet={k:v for k,v in packet.items() if k!="actions"} | {
                "top_actions": packet["actions"][:8]
            }
        print(json.dumps(packet,sort_keys=True))
        return 0
    except Exception as err:
        print(json.dumps({"status":"ORIGINAL_SEO_LIFECYCLE_HELD",
                          "reason_code":type(err).__name__,
                          "website_changed":False,"outbound_sent":False,
                          "database_writes":False}))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
