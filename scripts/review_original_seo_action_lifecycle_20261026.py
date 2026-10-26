#!/usr/bin/env python3
"""Daily SEO eyes/brain/hands review in the EXISTING organic SEO owner.

Input: original immutable daily Google index + weekly SEO growth receipts.
Execution: at most a bounded set of GET-only health checks on exact owned URLs.
Output: private immutable daily lifecycle snapshot for the existing Founder UI.
No new service, API writer, SEO publisher, DB schema, or outbound.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone, timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener
import fcntl

from empire_os.search_intelligence.seo_action_lifecycle_20261026 import (
    build_seo_action_lifecycle, _path, SEOActionHeld
)

ROOT = Path("/home/ubuntu/empire_releases/seo_daily_index_status_20261026")
WEEKLY = Path("/home/ubuntu/empire_releases/seo_weekly_gsc_two_page_20261022")
# Latest ORIGINAL governed AEO release. The earlier V1 direct-link receipt
# is historical; current HTML is the separately validated source-hint V2.
RELEASE = Path("/home/ubuntu/empire_releases/seo_aeo_entry_claim_v2_20261026_stage/activation_result.json")
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


class _OwnedRedirectOnly(HTTPRedirectHandler):
    """Never follow a purported first-party redirect onto an external host.

    The original SEO GET budget covers public pages ONLY; redirects may not
    widen that permission into unaudited third-party network requests.
    """
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target=urlsplit(newurl)
        if (target.scheme != "https" or target.netloc != "empire-ai.co.uk"
            or target.username or target.password
            or not target.path.startswith("/") or target.path.startswith("//")
            or target.query or target.fragment):
            raise SEOActionHeld("CROSS_ORIGIN_SEO_REDIRECT_HELD")
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def _read_only_page_check(url: str) -> dict:
    # Only bounded owned routes, no host, scheme, credentials or user parameters.
    route = _path(url)
    if route == "/":
        raise SEOActionHeld("ROOT_PAGE_NOT_ELIGIBLE_FOR_AUTOMATED_ACTION_TEST")
    request = Request("https://empire-ai.co.uk" + route,
                      headers={"User-Agent":"EmpireOS-SEO-Audit/1.0"},
                      method="GET")
    try:
        with build_opener(_OwnedRedirectOnly()).open(request, timeout=6) as response:
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


def _previous_receipt(root: Path, now: datetime) -> dict | None:
    """Last immutable private SEO receipt, max 48 hours old; never search web."""
    if not root.is_dir() or root.is_symlink():
        return None
    today = now.astimezone(timezone.utc).date()
    for days_ago in (1, 2):
        earlier = today - timedelta(days=days_ago)
        path = root / f"seo-actions-{earlier.isoformat()}.json"
        if not path.exists() and not path.is_symlink():
            continue
        if (path.is_symlink() or not path.is_file()
            or path.stat().st_uid != os.geteuid()
            or path.stat().st_mode & 0o077):
            raise SEOActionHeld("PREVIOUS_PRIVATE_SEO_RECEIPT_NOT_TRUSTED")
        previous = _trusted_json(path)
        if previous.get("schema_version") != "empire.search.seo_action_lifecycle.v1":
            raise SEOActionHeld("PREVIOUS_SEO_LIFECYCLE_SCHEMA_UNTRUSTED")
        return previous
    return None


def _validated_previous(previous: dict | None, now: datetime) -> dict:
    if previous is None:
        return {}
    if (not isinstance(previous, dict)
        or previous.get("schema_version") != "empire.search.seo_action_lifecycle.v1"
        or not isinstance(previous.get("actions"), list)
        or len(previous["actions"]) > 60
        or not isinstance(previous.get("weekly_source_as_of"), str)):
        raise SEOActionHeld("PREVIOUS_SEO_LIFECYCLE_SCHEMA_UNTRUSTED")
    try:
        stamped=datetime.fromisoformat(previous["observed_at"])
    except (KeyError, ValueError, TypeError) as e:
        raise SEOActionHeld("PREVIOUS_SEO_LIFECYCLE_CLOCK_INVALID") from e
    if (stamped.tzinfo is None or not timedelta(0) < now-stamped <= timedelta(hours=48)):
        raise SEOActionHeld("PREVIOUS_SEO_LIFECYCLE_OUTSIDE_FRESHNESS")
    mapping={}
    for item in previous["actions"]:
        if (not isinstance(item, dict) or not isinstance(item.get("id"), str)
            or not isinstance(item.get("url"), str)
            or not isinstance(item.get("reason_code"), str)):
            raise SEOActionHeld("PREVIOUS_SEO_LIFECYCLE_ACTION_UNTRUSTED")
        _path(item["url"])
        if item["id"] in mapping:
            raise SEOActionHeld("PREVIOUS_SEO_LIFECYCLE_DUPLICATE_ACTION")
        mapping[item["id"]]=item
    return mapping


def _previous_success(row: dict, prior: dict | None, *, unchanged_week: bool,
                      previous_observed_at: str | None, now: datetime) -> bool:
    if not unchanged_week or prior is None:
        return False
    test=prior.get("technical_test")
    # A cached result inherits the ORIGINAL GET time, never yesterday's
    # archive timestamp; repeated reuse cannot extend the freshness window.
    time_string=(test.get("initial_live_test_at_utc") if isinstance(test,dict) else None)
    time_string=time_string or previous_observed_at
    try:
        first_seen=datetime.fromisoformat(time_string)
    except (ValueError,TypeError):
        return False
    if first_seen.tzinfo is None or not timedelta(0)<now-first_seen<=timedelta(hours=48):
        return False
    if (prior.get("id") != row["id"] or prior.get("url") != row["url"]
        or prior.get("reason_code") != row["reason_code"]
        or prior.get("state") != "tested" or not isinstance(test, dict)):
        return False
    return (test.get("status") in {
                "TESTED_READ_ONLY_NO_MUTATION",
                "REUSED_RECENT_VERIFIED_TECHNICAL_TEST",
            }
            and test.get("http_status") == 200
            and test.get("self_canonical") is True
            and test.get("indexable") is True
            and test.get("html_content_type") is True
            and test.get("site_changed") is False
            and test.get("observed_source") == "live_first_party_https_GET"
            and isinstance(test.get("body_sha256"), str)
            and len(test["body_sha256"]) == 64)


def build_run(*, observed: datetime | None=None, get=None, previous: dict | None=None) -> dict:
    now=observed or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise SEOActionHeld("AWARE_CLOCK_REQUIRED")
    day=now.astimezone(timezone.utc).date().isoformat()
    daily=_trusted_json(ROOT / f"google-index-{day}.json")
    weekly=_trusted_json(_latest_weekly())
    release=_trusted_json(RELEASE)
    from scripts.review_live_organic_buyer_journey_20261024 import review
    from empire_os.gtm_ops_first_sale_source import observe_owner_ops_first_sale
    buyer=review()
    # The original privileged five-minute Ops Control is the sole canonical
    # DB reader. This SEO routine consumes only its safe validated counters.
    sales=observe_owner_ops_first_sale(Path("/srv/empire_os"),now=now)
    result=build_seo_action_lifecycle(
        weekly,daily,buyer_journey=buyer,aeo_release=release,
        ops_sales=sales,observed_at=now
    )
    prior_by_id=_validated_previous(previous, now)
    same_week=bool(previous and previous.get("weekly_source_as_of") == result["weekly_source_as_of"])
    getter=get or _read_only_page_check
    attempts=0
    reused=0
    new_count=0
    reopened=0
    for item in result["actions"]:
        past=prior_by_id.get(item["id"])
        if past is None:
            new_count+=1
            item["previous_state"] = None
        else:
            item["previous_state"] = past.get("state")
            if past.get("state") == "verified" and item["state"] != "verified":
                reopened+=1
                item["regression_review_required"] = True
        if (item["state"] == "staged" and _previous_success(
            item,past,unchanged_week=same_week,
            previous_observed_at=previous.get("observed_at") if previous else None,
            now=now,
        )):
            # Keep the original observation timestamp and source digest.
            # This is *not* a new live test. Revalidation resumes after 48h,
            # a new weekly GSC source or any observed regression.
            original=dict(past["technical_test"])
            original["status"]="REUSED_RECENT_VERIFIED_TECHNICAL_TEST"
            original["initial_live_test_at_utc"] = (
                original.get("initial_live_test_at_utc") or previous["observed_at"])
            original["reused_from_previous_day"]=True
            item["technical_test"]=original
            item["state"]="tested"
            item["state_path"]=["detected","prioritised","staged","tested"]
            item["next_action"]="PRIOR_LIVE_TECHNICAL_CHECK_STILL_WITHIN_REVIEW_WINDOW"
            reused+=1
            continue
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
        if isinstance(outcome,dict) and outcome.get("status")=="TESTED_READ_ONLY_NO_MUTATION":
            outcome["initial_live_test_at_utc"]=now.isoformat()
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
    result["milestone_reached_counts"]={
        name:sum(name in i["state_path"] for i in result["actions"])
        for name in result["lifecycle_states"]
    }
    result["read_only_technical_tests_executed"]=attempts
    result["previous_successful_tests_reused_not_rerun"]=reused
    result["new_action_ids_since_previous_receipt"]=new_count if previous else None
    result["reopened_verified_actions"]=reopened if previous else None
    result["prior_ids_missing_from_current_weekly_sample"]=(
        sum(action_id not in {a["id"] for a in result["actions"]}
            for action_id in prior_by_id) if previous else None
    )
    result["missing_actions_are_not_assumed_fixed"]=True
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
    previous=_previous_receipt(root,now)
    packet=build_run(observed=now,get=get,previous=previous)
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
            "previous_healthy_tests_reused":packet.get("previous_successful_tests_reused_not_rerun",0),
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
