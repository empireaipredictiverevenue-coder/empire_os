"""Durable official source coverage, per-day cursor and incomplete-run hygiene."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

import pytest

from empire_os.dobnow_incremental import (
    SCHEMA, PROGRESS_FILE, MAX_ROWS, observe_one_day, _read_progress,
)
from empire_os.lead_sources.nyc_dobnow import JOB

NOW=datetime(2026,10,18,12,0,tzinfo=timezone.utc)
DAY="2026-10-16"


class Pages:
    """40 + 40 + 5 selected-row pages, three different verified jobs."""
    def __init__(self,*,count=85):
        self.calls=[]
        self.count=count

    def page(self,*,now,issued_day,after_source_row_id):
        assert now==NOW and issued_day==DAY
        self.calls.append(after_source_row_id)
        offsets={None:0,"row-cursor.0":40,"row-cursor.1":80}
        assert after_source_row_id in offsets
        index=offsets[after_source_row_id]//40
        count=40 if index<2 else 5
        code=f"B{index:08d}-I1"
        assert JOB.fullmatch(code)
        event={
            "job_filing_number":code,"filing_date":"2026-01-01",
            "first_permit_date":DAY,"issued_date":DAY,
            "filing_reason":"Initial Permit","permit_status":"Permit Issued",
            "work_type":"General Construction",
            "work_types":["General Construction"],
            "underlying_permit_row_count":1,
            "borough":"Brooklyn","bin":"3002642","bbl":"3002697501",
            "solar_work_type":False,
            "general_construction_work_type":True,
            "official_event_crosscheck":True,
        }
        return {
            "status":"OFFICIAL_BOUNDED_EVENT_CROSSCHECK","mode":"OBSERVE",
            "no_sales_authority":True,"query_rows":count,
            "issued_day":DAY,
            "last_source_row_id":f"row-cursor.{index}",
            "source_response_sha256":{"permits":str(index),"filings":"fixture"},
            "events":[event],
        }

    def count_day(self,day):
        assert day==DAY
        return {"count":self.count,"sha256":"fixture_sha"}


class Writer:
    def __init__(self):
        self.jobs=set()
        self.calls=0
        self.fail=False

    def __call__(self,candidates):
        self.calls+=1
        if self.fail:
            raise RuntimeError("inbox write failure")
        results=[]
        for c in candidates:
            assert c.source=="permits_nyc_dobnow"
            assert not c.phone and not c.email
            self.jobs.add(c.raw["job_filing_number"])
            results.append({"source":c.source,"execution_authority":"none",
                            "decision":"created"})
        return results


def observe(root,pages,writer,*,commit=False,max_pages=2,now=NOW):
    return observe_one_day(
        DAY,root=root,now=now,commit=commit,
        max_pages=max_pages,fetch_page=pages.page,
        count_source_rows=pages.count_day,batch_writer=writer,
    )


def test_preview_is_pure_no_files_or_buyer_data(tmp_path):
    pages=Pages();writer=Writer()
    r=observe(tmp_path,pages,writer,commit=False,max_pages=2)
    assert r["status"]=="INCOMPLETE_DATE_PARTITION"
    assert r["source_rows_cumulative"]==80
    assert r["verified_events_staged"]==2
    assert pages.calls==[None,"row-cursor.0"]
    assert writer.calls==0
    assert not (tmp_path/PROGRESS_FILE).exists()


def test_bounded_resumption_only_commits_full_source_day(tmp_path,monkeypatch):
    monkeypatch.setenv("EMPIRE_DOBNOW_PERMIT_SOURCE_ENABLED","1")
    pages=Pages();writer=Writer()
    a=observe(tmp_path,pages,writer,commit=True,max_pages=2)
    assert a["source_completed_and_committed"] is False
    assert writer.calls==0
    path=tmp_path/PROGRESS_FILE
    state=_read_progress(path)
    assert path.stat().st_mode&0o777==0o600
    assert state["days"][DAY]["source_permit_rows"]==80
    assert state["days"][DAY]["coverage"]=="INCOMPLETE_BOUNDED_KEYSET"
    b=observe(tmp_path,pages,writer,commit=True,max_pages=2)
    assert b["status"]=="DATE_PARTITION_COMPLETE"
    assert b["source_rows_cumulative"]==85
    assert b["official_day_count_at_completion"]==85
    assert len(writer.jobs)==3
    assert writer.calls==1
    assert pages.calls==[None,"row-cursor.0","row-cursor.1"]
    completed=_read_progress(path)["days"][DAY]
    assert completed["verified_job_events"]==3
    assert completed["coverage"]=="COMPLETE_DATE_PARTITION_AT_OBSERVATION_ONLY"
    assert "staged" not in completed
    c=observe(tmp_path,pages,writer,commit=True,max_pages=2,now=NOW+timedelta(hours=1))
    assert c["status"]=="COMPLETED_SNAPSHOT_NOT_YET_DUE_FOR_RECHECK"
    assert len(pages.calls)==3


def test_count_mismatch_resets_cursor_and_does_not_publish(tmp_path,monkeypatch):
    monkeypatch.setenv("EMPIRE_DOBNOW_PERMIT_SOURCE_ENABLED","1")
    p=Pages(count=99);writer=Writer()
    observe(tmp_path,p,writer,commit=True,max_pages=2)
    outcome=observe(tmp_path,p,writer,commit=True,max_pages=2)
    assert outcome["status"]=="SOURCE_ROW_COUNT_MISMATCH_HELD"
    assert outcome["source_completed_and_committed"] is False
    assert writer.calls==0
    state=_read_progress(tmp_path/PROGRESS_FILE)["days"][DAY]
    assert state["coverage"]=="COUNT_MISMATCH_RESTART_REQUIRED"
    assert "last_source_row_id" not in state
    r=observe(tmp_path,p,writer,commit=True,max_pages=1)
    assert r["status"]=="INCOMPLETE_DATE_PARTITION"
    assert p.calls[-1] is None


def test_inbox_writer_failure_does_not_advance_complete_cursor(tmp_path,monkeypatch):
    monkeypatch.setenv("EMPIRE_DOBNOW_PERMIT_SOURCE_ENABLED","1")
    p=Pages();w=Writer()
    observe(tmp_path,p,w,commit=True,max_pages=2)
    w.fail=True
    with pytest.raises(RuntimeError,match="inbox write failure"):
        observe(tmp_path,p,w,commit=True,max_pages=2)
    pending=_read_progress(tmp_path/PROGRESS_FILE)["days"][DAY]
    assert pending["coverage"]=="SOURCE_DATE_SCAN_FINISHED_NOT_YET_COMMITTED"
    assert pending["source_permit_rows"]==85
    w.fail=False
    # Re-run from the last cursor; this returns no rows and must not lose
    # staged events. Source count still proves whole-day coverage.
    def empty(*,now,issued_day,after_source_row_id):
        assert after_source_row_id=="row-cursor.2"
        return {"mode":"OBSERVE","no_sales_authority":True,"query_rows":0,
                "issued_day":DAY,"last_source_row_id":None,
                "source_response_sha256":{"permits":"empty","filings":"none"},
                "events":[]}
    a=observe_one_day(DAY,root=tmp_path,now=NOW,commit=True,
                      fetch_page=empty,count_source_rows=p.count_day,
                      batch_writer=w)
    assert a["status"]=="DATE_PARTITION_COMPLETE"
    assert len(w.jobs)==3


def test_activation_flag_is_required_even_for_temp_path(tmp_path,monkeypatch):
    monkeypatch.delenv("EMPIRE_DOBNOW_PERMIT_SOURCE_ENABLED",raising=False)
    p=Pages();w=Writer()
    with pytest.raises(PermissionError,match="ENABLE_FLAG_REQUIRED"):
        observe(tmp_path,p,w,commit=True)
    assert w.calls==0 and p.calls==[]
    assert not (tmp_path/PROGRESS_FILE).exists()


def test_corrupt_progress_fails_closed_no_truncation(tmp_path,monkeypatch):
    monkeypatch.setenv("EMPIRE_DOBNOW_PERMIT_SOURCE_ENABLED","1")
    path=tmp_path/PROGRESS_FILE;path.parent.mkdir(parents=True)
    path.write_text("{invalid")
    before=path.read_bytes()
    with pytest.raises(json.JSONDecodeError):
        observe(tmp_path,Pages(),Writer(),commit=True)
    assert path.read_bytes()==before


def test_day_and_page_budget_inputs_rejected(tmp_path,monkeypatch):
    monkeypatch.setenv("EMPIRE_DOBNOW_PERMIT_SOURCE_ENABLED","1")
    with pytest.raises(ValueError):
        observe_one_day("2026-10-31",root=tmp_path,now=NOW,commit=False)
    with pytest.raises(ValueError):
        observe_one_day("2026-10-16' OR 1=1",root=tmp_path,now=NOW)
    with pytest.raises(ValueError):
        observe_one_day(DAY,root=tmp_path,now=NOW,max_pages=11)
    with pytest.raises(ValueError):
        observe_one_day(DAY,root=tmp_path,now=NOW,max_pages=True)


def test_day_selector_prioritises_resumable_partitions_over_new_days(
    tmp_path,monkeypatch
):
    from empire_os.dobnow_incremental import next_unfinished_day
    monkeypatch.setenv("EMPIRE_DOBNOW_PERMIT_SOURCE_ENABLED","1")
    assert next_unfinished_day(root=tmp_path,now=NOW)=="2026-10-18"
    p=Pages();w=Writer()
    observe(tmp_path,p,w,commit=True,max_pages=1)
    assert next_unfinished_day(root=tmp_path,now=NOW)==DAY
    # Even when the default today's partition is missing, finish the in-flight
    # 16 Oct partition first rather than skipping the saved cursor.
    r=observe(tmp_path,p,w,commit=True,max_pages=2)
    assert r["status"]=="DATE_PARTITION_COMPLETE"
    assert next_unfinished_day(root=tmp_path,now=NOW)=="2026-10-18"


def test_current_sample_partition_keyset_and_untrusted_row_id_fail_closed():
    from empire_os.lead_sources.nyc_dobnow import current_event_sample
    class Response:
        content=b'[{"source_row_id":"row-a123","job_filing_number":"B01222111-I1",'+(
            b'"issued_date":"2026-10-16T00:00:00.000",'
            b'"filing_reason":"Initial Permit"}]')
        def raise_for_status(self): pass
    class TestClient:
        def __init__(self): self.requests=[]
        def get(self,url,*,params,timeout,headers):
            self.requests.append((url,params))
            return Response()
    fake=TestClient()
    review=current_event_sample(now=NOW,issued_day=DAY,
                                after_source_row_id="row-a122",client=fake)
    assert review["issued_day"]==DAY
    assert review["last_source_row_id"]=="row-a123"
    assert review["events"]==[]  # no matching DOB job filing record
    permit_request=fake.requests[0][1]
    assert ":id as source_row_id" in permit_request["$select"]
    assert ":id > 'row-a122'" in permit_request["$where"]
    assert permit_request["$order"]==":id ASC"
    assert "$offset" not in permit_request
    with pytest.raises(ValueError,match="UNSAFE_OFFICIAL_SOURCE_ROW_CURSOR"):
        current_event_sample(now=NOW,issued_day=DAY,
                             after_source_row_id="x' OR 1=1")
    with pytest.raises(ValueError,match="UNSAFE_OFFICIAL_SOURCE_ROW_CURSOR"):
        current_event_sample(now=NOW,after_source_row_id="row-a123")
