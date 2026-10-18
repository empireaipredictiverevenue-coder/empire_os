"""NYC DOB NOW official current permit *events*, never inferred lead identities.

Two official NYC Open Data endpoints, <=40 initial permit rows per invocation.
All source rows must have independently matching DOB filing + permit job/BBL/BIN,
the real original issuance date, and no owner/permittee/contact export. This is
strictly an incomplete bounded source *sample*, not comprehensive city coverage.

Only the EXISTING crawler may enqueue evidence; an exact explicit enable flag is
required before it will execute in a scheduled all-source crawl.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
import re
from typing import Iterator

import requests

from empire_os.lead_sources import LeadCandidate, SourceInfo

FILINGS_ID = "w9ak-ipjd"
ISSUED_ID = "rbx6-tga4"
HOST = "https://data.cityofnewyork.us"
FILINGS_URL = f"{HOST}/resource/{FILINGS_ID}.json"
PERMITS_URL = f"{HOST}/resource/{ISSUED_ID}.json"
DATASET_PAGE = f"{HOST}/d/{ISSUED_ID}"
SOURCE = "permits_nyc_dobnow"
ENABLE_FLAG = "EMPIRE_DOBNOW_PERMIT_SOURCE_ENABLED"
MAX_ROWS = 40
MAX_PAGES = 10  # strictly bounded to 400 source rows per enabled run
LOOKBACK_DAYS = 7
JOB = re.compile(r"[BMQSX]\d{8}-[A-Z]\d{1,2}\Z")
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?\Z")


def _day(value: object):
    if not isinstance(value, str) or not ISO_DATE.fullmatch(value):
        return None
    try:
        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _rows(url: str, params: dict, *, client=requests) -> tuple[list[dict], str]:
    if url not in (FILINGS_URL, PERMITS_URL):
        raise ValueError("UNAPPROVED_PROVIDER_URL")
    response = client.get(
        url, params=params, timeout=15, headers={"Accept": "application/json"},
    )
    response.raise_for_status()
    body = response.content
    if len(body) > 180_000:
        raise ValueError("SOURCE_RESPONSE_TOO_LARGE")
    result = json.loads(body)
    if not isinstance(result, list) or len(result) > MAX_ROWS:
        raise ValueError("SOURCE_RESPONSE_NOT_BOUNDED")
    if any(not isinstance(row, dict) for row in result):
        raise ValueError("SOURCE_ROW_NOT_OBJECT")
    return result, sha256(body).hexdigest()


def current_event_sample(*, now: datetime | None = None, offset: int = 0, client=requests) -> dict:
    """Bounded read-only first-issuance/filing join; no DB, mail, or service.

    The query deliberately reads no names, phone numbers, addresses, free-text
    job descriptions, applicants or property owner identities.
    """
    if type(offset) is not int or not 0 <= offset < MAX_ROWS * MAX_PAGES or offset % MAX_ROWS:
        raise ValueError("UNSAFE_PERMIT_PAGE_OFFSET")
    today = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    since = (today - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%dT00:00:00")
    permit_params = {
        "$select": ("job_filing_number,issued_date,approved_date,filing_reason,"
                    "work_type,permit_status,borough,bin,bbl"),
        "$where": f"issued_date >= '{since}' AND filing_reason = 'Initial Permit'",
        "$order": "issued_date DESC, job_filing_number ASC",
        "$limit": MAX_ROWS,
        "$offset": offset,
    }
    permits, permits_sha = _rows(PERMITS_URL, permit_params, client=client)
    jobs = []
    for p in permits:
        job = p.get("job_filing_number")
        if not isinstance(job, str) or JOB.fullmatch(job) is None:
            # Do not build a query from an unvalidated source-controlled ID.
            continue
        jobs.append(job)
    # Multiple work permits can share ONE DOB NOW job filing number.
    # Read one filing per DISTINCT job and group first-issued permit types,
    # rather than counting each work permit as a separate construction project.
    jobs = sorted(set(jobs))
    if not jobs:
        return {
            "status": "NO_BOUNDED_INITIAL_PERMIT_ROWS", "mode": "OBSERVE",
            "events": [], "query_rows": len(permits), "page_offset": offset,
            "sample_may_be_incomplete": False,
            "source_response_sha256": {"permits": permits_sha},
            "no_sales_authority": True,
        }
    filing_params = {
        "$select": ("job_filing_number,filing_date,first_permit_date,"
                    "filing_status,job_type,borough,bin,bbl,"
                    "solar_work_type_,general_construction_work_type_"),
        "$where": "job_filing_number in (" +
                  ",".join("'" + job + "'" for job in jobs) + ")",
        "$limit": MAX_ROWS,
    }
    filings, filings_sha = _rows(FILINGS_URL, filing_params, client=client)
    if len(filings) != len(set(str(f.get("job_filing_number")) for f in filings)):
        raise ValueError("DUPLICATE_SOURCE_FILING_JOB")
    indexed = {f.get("job_filing_number"): f for f in filings}
    events_by_job = {}
    for p in permits:
        job = p.get("job_filing_number")
        if not isinstance(job, str) or not JOB.fullmatch(job):
            continue
        f = indexed.get(job)
        if not f:
            continue
        issued = _day(p.get("issued_date"))
        first = _day(f.get("first_permit_date"))
        filed = _day(f.get("filing_date"))
        if (issued is None or first is None or filed is None
                or not timedelta(0) <= today - issued <= timedelta(days=LOOKBACK_DAYS)
                or not filed <= first == issued
                or p.get("permit_status") != "Permit Issued"
                or p.get("filing_reason") != "Initial Permit"):
            continue
        # There is no implication that DOB and DCP are independent here:
        # this is a two-DOB-dataset official event cross-check.
        if (any(not isinstance(p.get(k), str)
                or not isinstance(f.get(k), str)
                or p.get(k).strip().upper() != f.get(k).strip().upper()
                for k in ("borough", "bin", "bbl"))
                or not re.fullmatch(r"\d{7}", p["bin"])
                or not re.fullmatch(r"\d{10}", p["bbl"])
                or len(p["borough"]) > 24):
            continue
        work = p.get("work_type")
        if not isinstance(work, str) or len(work) > 60:
            continue
        solar = f.get("solar_work_type_") == "YES"
        general = f.get("general_construction_work_type_") == "YES"
        event = {
            "job_filing_number": job, "filing_date": filed.date().isoformat(),
            "first_permit_date": first.date().isoformat(),
            "issued_date": issued.date().isoformat(),
            "filing_reason": "Initial Permit", "permit_status": "Permit Issued",
            "work_type": work, "work_types": [work],
            "underlying_permit_row_count": 1,
            "borough": p["borough"].title(),
            "bin": p["bin"], "bbl": p["bbl"], "solar_work_type": solar,
            "general_construction_work_type": general,
            "official_event_crosscheck": True,
        }
        existing = events_by_job.get(job)
        if existing is None:
            events_by_job[job] = event
        else:
            if (any(existing.get(k) != event.get(k) for k in (
                    "filing_date", "first_permit_date", "issued_date",
                    "bin", "bbl", "borough", "permit_status", "filing_reason"
            ))):
                raise ValueError("CONFLICTING_WORK_PERMITS_SAME_JOB")
            existing["work_types"] = sorted(set(existing["work_types"] + [work]))
            existing["work_type"] = (existing["work_types"][0]
                                     if len(existing["work_types"]) == 1
                                     else "Multiple Work Types")
            existing["underlying_permit_row_count"] += 1
    events = list(events_by_job.values())
    events.sort(key=lambda x: (x["issued_date"], x["job_filing_number"]), reverse=True)
    return {
        "status": "OFFICIAL_BOUNDED_EVENT_CROSSCHECK",
        "mode": "OBSERVE",
        "source_platform": "NYC Open Data",
        "source_datasets": [FILINGS_ID, ISSUED_ID],
        "observed_at_utc": today.isoformat(),
        "events": events,
        "query_rows": len(permits),
        "page_offset": offset,
        "distinct_crosschecked_jobs": len(events),
        "duplicate_work_permit_rows_collapsed": sum(
            event["underlying_permit_row_count"] - 1 for event in events
        ),
        "sample_may_be_incomplete": len(permits) == MAX_ROWS,
        "source_response_sha256": {"permits": permits_sha, "filings": filings_sha},
        "independent_site_or_buyer_verified": False,
        "no_sales_authority": True,
    }


def to_signal_candidates(review: dict) -> Iterator[LeadCandidate]:
    if (review.get("status") != "OFFICIAL_BOUNDED_EVENT_CROSSCHECK"
            or review.get("mode") != "OBSERVE"
            or review.get("no_sales_authority") is not True):
        raise ValueError("UNTRUSTED_DOBNOW_REVIEW")
    for item in review["events"]:
        job = item["job_filing_number"]
        if JOB.fullmatch(job) is None:
            raise ValueError("UNTRUSTED_JOB_ID")
        # Direct official dataset view rather than fabricated old BIS portal URL.
        yield LeadCandidate(
            name=f"NYC DOB NOW Permit {job}", niche="general_contractor",
            metro="NYC", state="NY", country_code="US",
            source=SOURCE, phone="", email="",
            url=f"{DATASET_PAGE}",
            details=f"NYC DOB NOW {job}: first permit issued {item['issued_date']}",
            lead_score=40,
            raw=dict(item),
        )


def run(metro: str | None = None) -> Iterator[LeadCandidate]:
    if metro not in (None, "NYC") or os.getenv(ENABLE_FLAG) != "1":
        return
    # One existing source run, bounded 10 pages maximum; no new timer or
    # client.  Overlap is deduplicated by the existing source signal ID.
    seen_jobs = set()
    for page in range(MAX_PAGES):
        review = current_event_sample(offset=page * MAX_ROWS)
        for candidate in to_signal_candidates(review):
            job = candidate.raw["job_filing_number"]
            if job not in seen_jobs:
                seen_jobs.add(job)
                yield candidate
        if review["query_rows"] < MAX_ROWS:
            break


def register_source(reg):
    reg(SourceInfo(
        name="permits_dobnow", tier="real", requires=[ENABLE_FLAG],
        description="GATED NYC DOB NOW verified first-issuance events, bounded <=40",
        run_fn=run,
    ))
