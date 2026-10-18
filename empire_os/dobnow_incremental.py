"""Crash-replay-safe DOB NOW daily keyset coverage, gated behind existing crawler.

Existing acquisition signal inbox remains the only event store. Progress is a
private source watermark/staging receipt, never a customer or buyer database.
A complete date partition is required before promoting its project evidence to
the existing inbox. No contact details or free-text fields are ingested.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
import fcntl
import json
import os
import re
import tempfile

from empire_os.lead_sources.nyc_dobnow import (
    ENABLE_FLAG, FILINGS_ID, ISSUED_ID, LOOKBACK_DAYS, MAX_PAGES, MAX_ROWS,
    PERMITS_URL, _rows, current_event_sample, to_signal_candidates,
)
from empire_os.signal_inbox import enqueue_signals_batch

SCHEMA = "empire.dobnow_daily_keyset_progress.v1"
PROGRESS_FILE = "runtime/acquisition/dobnow_daily_keyset_progress.json"
LOCK_FILE = "runtime/acquisition/dobnow_daily_keyset_progress.lock"
MAX_STAGED_JOBS = 1200
MAX_DAYS = LOOKBACK_DAYS + 1
# A completed day is a source snapshot, not permanently final: source rows may
# be amended/backfilled. Observe it again at most once per 24h while in window.
RECHECK_HOURS = 24


def _utc(now: datetime | None) -> datetime:
    date = (now or datetime.now(timezone.utc))
    if date.tzinfo is None or date.utcoffset() is None:
        raise ValueError("NAIVE_OBSERVATION_CLOCK")
    return date.astimezone(timezone.utc)


def _validate_day(day: str, now: datetime) -> None:
    if not isinstance(day, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}",day):
        raise ValueError("INVALID_PERMIT_DAY")
    try:
        issued = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
    except ValueError as ex:
        raise ValueError("INVALID_PERMIT_DAY") from ex
    if not now.date()-timedelta(days=LOOKBACK_DAYS) <= issued.date() <= now.date():
        raise ValueError("OUTSIDE_BOUNDED_DOBNOW_LOOKBACK")


def _read_progress(path: Path) -> dict:
    if not path.exists():
        return {"schema": SCHEMA, "mode": "OBSERVE", "days": {},
                "execution_authority": "none"}
    if path.is_symlink() or path.stat().st_size > 2_000_000:
        raise ValueError("UNSAFE_DOBNOW_PROGRESS_PATH")
    data=json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or data.get("schema") != SCHEMA
            or data.get("mode") != "OBSERVE"
            or data.get("execution_authority") != "none"
            or not isinstance(data.get("days"),dict)):
        raise ValueError("UNTRUSTED_DOBNOW_PROGRESS_STATE")
    if len(data["days"])>MAX_DAYS:
        raise ValueError("UNBOUNDED_DOBNOW_PROGRESS_STATE")
    return data


def _atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("UNSAFE_DOBNOW_PROGRESS_PATH")
    data=(json.dumps(payload,sort_keys=True,indent=2)+"\n").encode()
    if len(data)>2_000_000:
        raise ValueError("OVERSIZED_DOBNOW_PROGRESS_STATE")
    fd, temp=tempfile.mkstemp(prefix=".dobnow_keyset.",suffix=".tmp",dir=path.parent)
    try:
        with os.fdopen(fd,"wb") as f:
            os.fchmod(f.fileno(),0o600)
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def official_day_row_count(day: str) -> dict:
    """One bounded Socrata count, same exact issuance/status filter as scanner."""
    params={
        "$select":"count(*) as source_total",
        "$where":f"issued_date = '{day}T00:00:00' AND filing_reason = 'Initial Permit'",
        "$limit":1,
    }
    from empire_os.lead_sources import nyc_dobnow
    rows, sha = nyc_dobnow._rows(PERMITS_URL, params)
    if (len(rows)!=1 or not isinstance(rows[0].get("source_total"), str)
            or not rows[0]["source_total"].isdigit()):
        raise ValueError("UNTRUSTED_OFFICIAL_DAY_COUNT")
    count=int(rows[0]["source_total"])
    if count<0 or count>100000:
        raise ValueError("UNBOUNDED_OFFICIAL_DAY_COUNT")
    return {"count":count,"sha256":sha}


def _merge(staged: dict, event: dict) -> None:
    job=event["job_filing_number"]
    existing=staged.get(job)
    if existing is None:
        if len(staged)>=MAX_STAGED_JOBS:
            raise ValueError("DOBNOW_DAY_JOB_BUDGET_EXCEEDED")
        staged[job]=dict(event)
        return
    stable=("job_filing_number","filing_date","first_permit_date","issued_date",
            "filing_reason","permit_status","borough","bin","bbl",
            "solar_work_type","general_construction_work_type")
    if any(existing.get(key)!=event.get(key) for key in stable):
        raise ValueError("DOBNOW_DUPLICATE_JOB_SOURCE_CONFLICT")
    # One project filing can have multiple distinct work-permit records.
    existing["work_types"]=sorted(set(existing["work_types"]+event["work_types"]))
    existing["work_type"]=(existing["work_types"][0] if len(existing["work_types"])==1
                           else "Multiple Work Types")
    existing["underlying_permit_row_count"]+=event["underlying_permit_row_count"]


def _finish_day(staged: dict, batch_writer: Callable, now: datetime) -> dict:
    candidates=list(to_signal_candidates({
        "status":"OFFICIAL_BOUNDED_EVENT_CROSSCHECK",
        "mode":"OBSERVE","no_sales_authority":True,
        "events":[staged[job] for job in sorted(staged)]
    }))
    results=[]
    # Existing atomic inbox writer is bounded to <=400 per call; a resumed
    # source day might contain more. A crash between chunks safely replays.
    for start in range(0,len(candidates),MAX_ROWS*MAX_PAGES):
        result=batch_writer(candidates[start:start+MAX_ROWS*MAX_PAGES])
        if len(result)!=len(candidates[start:start+MAX_ROWS*MAX_PAGES]):
            raise ValueError("INCOMPLETE_DOBNOW_SIGNAL_COMMIT")
        results.extend(result)
    if any(r.get("execution_authority")!="none"
           or r.get("source")!="permits_nyc_dobnow" for r in results):
        raise ValueError("INVALID_SIGNAL_COMMIT_RECEIPT")
    return {
        "snapshot_completed_at_utc":now.isoformat(),
        "verified_job_events":len(candidates),
        "signal_results":len(results),
        "coverage":"COMPLETE_DATE_PARTITION_AT_OBSERVATION_ONLY",
    }


def next_unfinished_day(*, root: Path = Path("/srv/empire_os"),
                        now: datetime | None = None) -> str | None:
    """Prioritise in-flight pages, then new date partitions, then due rechecks."""
    at=_utc(now)
    state=_read_progress(Path(root)/PROGRESS_FILE)
    days=[(at.date()-timedelta(days=i)).isoformat()
          for i in range(LOOKBACK_DAYS+1)]
    records=state["days"]
    for day in days:
        r=records.get(day)
        if isinstance(r,dict) and r.get("coverage") in (
            "INCOMPLETE_BOUNDED_KEYSET",
            "SOURCE_DATE_SCAN_FINISHED_NOT_YET_COMMITTED",
            "COUNT_MISMATCH_RESTART_REQUIRED",
        ):
            return day
    for day in days:
        if day not in records:
            return day
    for day in days:
        r=records.get(day)
        if not isinstance(r,dict):
            return day
        stamp=r.get("snapshot_completed_at_utc")
        if not isinstance(stamp,str):
            return day
        try:
            age=at-datetime.fromisoformat(stamp).astimezone(timezone.utc)
        except (TypeError,ValueError,OverflowError,AttributeError):
            raise ValueError("INVALID_COMPLETED_SOURCE_RECEIPT")
        if age>=timedelta(hours=RECHECK_HOURS):
            return day
    return None


def observe_one_day(
    day: str, *, root: Path = Path("/srv/empire_os"),
    now: datetime | None = None,
    commit: bool = False,
    max_pages: int = MAX_PAGES,
    fetch_page: Callable = current_event_sample,
    batch_writer: Callable = enqueue_signals_batch,
    count_source_rows: Callable = official_day_row_count,
) -> dict[str, Any]:
    """Advance <=max_pages of a single official date; no scheduling.

    commit=False is purely in-memory/read-only, even if the env flag is set.
    commit=True requires the exact explicit existing official-source flag.
    A partially scanned date only enters the private staging receipt.
    """
    at=_utc(now)
    _validate_day(day,at)
    if type(max_pages) is not int or not 1<=max_pages<=MAX_PAGES:
        raise ValueError("INVALID_DOBNOW_PAGE_BUDGET")
    root=Path(root).resolve()
    if commit and os.getenv(ENABLE_FLAG)!="1":
        raise PermissionError("DOBNOW_EXISTING_SOURCE_ENABLE_FLAG_REQUIRED")
    state_path=root/PROGRESS_FILE
    lock_path=root/LOCK_FILE
    if not commit:
        state=_read_progress(state_path)
        return _scan(day,at,state,False,max_pages,fetch_page,batch_writer,
                     count_source_rows,None)
    # Existing source-lock strategy; no second scheduler/bus/new DB.
    lock_path.parent.mkdir(parents=True,exist_ok=True)
    if lock_path.is_symlink():
        raise ValueError("UNSAFE_DOBNOW_PROGRESS_LOCK")
    lock_path.touch(exist_ok=True)
    os.chmod(lock_path, 0o600)
    with lock_path.open("r+") as locked:
        fcntl.flock(locked.fileno(), fcntl.LOCK_EX)
        try:
            state=_read_progress(state_path)
            return _scan(day,at,state,True,max_pages,fetch_page,batch_writer,
                         count_source_rows,state_path)
        finally:
            fcntl.flock(locked.fileno(), fcntl.LOCK_UN)


def _scan(day: str, now: datetime, state: dict, commit: bool,
          max_pages: int, fetch_page: Callable, batch_writer: Callable,
          count_source_rows: Callable, state_path: Path | None) -> dict:
    existing=dict(state.get("days",{}).get(day) or {})
    if existing.get("coverage")=="COMPLETE_DATE_PARTITION_AT_OBSERVATION_ONLY":
        completed=existing.get("snapshot_completed_at_utc")
        try:
            last=datetime.fromisoformat(completed)
            elapsed=now-last.astimezone(timezone.utc)
        except (TypeError,ValueError,OverflowError,AttributeError):
            raise ValueError("INVALID_COMPLETED_SOURCE_RECEIPT")
        if timedelta(0)<=elapsed<timedelta(hours=RECHECK_HOURS):
            return {
                "status":"COMPLETED_SNAPSHOT_NOT_YET_DUE_FOR_RECHECK",
                "day":day,"read_only":not commit,"source_rows_this_run":0,
                "verified_events_staged":0,
                "coverage":existing["coverage"],"execution_authority":"none",
            }
        # Same issued-date partition is rechecked after a day, to detect
        # delayed records and official corrections. Inbox events deduplicate.
        existing={}
    staged=dict(existing.get("staged") or {})
    if len(staged)>MAX_STAGED_JOBS:
        raise ValueError("CORRUPT_OVER_BUDGET_DOBNOW_STAGING")
    after=existing.get("last_source_row_id")
    if after is not None and (
        not isinstance(after,str)
        or re.fullmatch(r"row-[a-z0-9._~-]{4,60}",after) is None):
        raise ValueError("CORRUPT_DOBNOW_SOURCE_CURSOR")
    row_count=int(existing.get("source_permit_rows") or 0)
    receipts=list(existing.get("page_receipts") or [])
    finished=False
    new_pages=0
    new_rows=0
    for _ in range(max_pages):
        review=fetch_page(now=now, issued_day=day, after_source_row_id=after)
        if review.get("mode")!="OBSERVE" or review.get("no_sales_authority") is not True:
            raise ValueError("UNTRUSTED_DOBNOW_PAGE")
        if review.get("issued_day")!=day:
            raise ValueError("SOURCE_DAY_MISMATCH")
        count=review["query_rows"]
        cursor=review.get("last_source_row_id")
        if type(count) is not int or not 0<=count<=MAX_ROWS:
            raise ValueError("UNBOUNDED_DOBNOW_SOURCE_PAGE")
        if count>0 and (not isinstance(cursor,str) or cursor==after
                        or re.fullmatch(r"row-[a-z0-9._~-]{4,60}",cursor) is None):
            raise ValueError("OFFICIAL_CURSOR_NOT_ADVANCING")
        for event in review.get("events",()):
            if event.get("issued_date")!=day:
                raise ValueError("OFFICIAL_EVENT_DATE_NOT_IN_PARTITION")
            _merge(staged,event)
        row_count+=count
        new_rows+=count
        new_pages+=1
        receipts.append({
            "end_row_id":cursor,"row_count":count,
            "source_response_sha256":review["source_response_sha256"],
        })
        after=cursor or after
        if count<MAX_ROWS:
            finished=True
            break
    official_total=None
    official_total_sha=None
    if finished:
        total_receipt=count_source_rows(day)
        if (not isinstance(total_receipt,dict)
                or type(total_receipt.get("count")) is not int
                or total_receipt["count"]<0):
            raise ValueError("INVALID_SOURCE_COMPLETENESS_RECEIPT")
        official_total=total_receipt["count"]
        official_total_sha=total_receipt.get("sha256")
        if official_total!=row_count:
            if commit:
                # An updated provider snapshot invalidates offset/keyset
                # consistency. Retry day from the first row next run.
                state["days"][day]={
                    "coverage":"COUNT_MISMATCH_RESTART_REQUIRED",
                    "observed_source_rows":row_count,
                    "official_count_at_finish":official_total,
                    "last_observed_at_utc":now.isoformat(),
                }
                _atomic(state_path,state)
            return {
                "status":"SOURCE_ROW_COUNT_MISMATCH_HELD",
                "day":day,"read_only":not commit,
                "source_rows_cumulative":row_count,
                "official_count_at_finish":official_total,
                "source_completed_and_committed":False,
                "execution_authority":"none","outreach_sent":False,
            }
    progress={
        "last_source_row_id":after,
        "source_permit_rows":row_count,
        "page_count":len(receipts),
        "page_receipts":receipts[-80:],
        "verified_job_events_staged":len(staged),
        "staged":staged,
        "coverage":"INCOMPLETE_BOUNDED_KEYSET" if not finished
                    else "SOURCE_DATE_SCAN_FINISHED_NOT_YET_COMMITTED",
        "last_observed_at_utc":now.isoformat(),
        "official_day_count_at_completion":official_total,
        "official_day_count_response_sha256":official_total_sha,
    }
    if commit:
        state["days"][day]=progress
        # Drop states that are outside the rolling 7-day window. This
        # bounds private saved PII-free source receipts, not the signal inbox.
        state["days"]={
            k:v for k,v in state["days"].items()
            if isinstance(k,str) and k>=(
                now-timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
        }
        if len(state["days"])>MAX_DAYS:
            raise ValueError("OVER_BUDGET_DAILY_CURSOR_STATES")
        _atomic(state_path,state)
        if finished:
            receipt=_finish_day(staged,batch_writer,now)
            progress.update(receipt)
            progress.pop("staged")
            state["days"][day]=progress
            _atomic(state_path,state)
    return {
        "status": "DATE_PARTITION_COMPLETE" if finished and commit
                 else "DATE_PARTITION_READY_TO_COMMIT" if finished
                 else "INCOMPLETE_DATE_PARTITION",
        "day":day,"read_only":not commit,
        "source_rows_this_run":new_rows,"source_rows_cumulative":row_count,
        "pages_this_run":new_pages,
        "verified_events_staged":len(staged),
        "last_source_row_id":after,
        "coverage":progress["coverage"],
        "official_day_count_at_completion":official_total,
        "source_completed_and_committed":finished and commit,
        "execution_authority":"none","outreach_sent":False,
    }
