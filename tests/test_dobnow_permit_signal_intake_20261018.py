"""Official DOB NOW event goes through existing signal-only inbox, never CRM."""
import json
from datetime import datetime, timezone, timedelta

import pytest

from empire_os import signal_inbox
from empire_os.candidate_quality import assess_candidate
from empire_os.lead_sources import _import_sources, get_source
from empire_os.lead_sources.nyc_dobnow import (
    SOURCE, FILINGS_URL, PERMITS_URL, current_event_sample, run,
    to_signal_candidates,
)
from empire_os.signal_resolver import candidate_from_signal

NOW = datetime(2026, 10, 18, 11, 30, tzinfo=timezone.utc)
JOB = "B01222111-I1"
BID = "3002642"
BBL = "3002697501"


def permit(**overrides):
    return {
        "job_filing_number": JOB,
        "issued_date": "2026-10-16T00:00:00.000",
        "approved_date": "2026-05-01T00:00:00.000",
        "filing_reason": "Initial Permit", "work_type": "General Construction",
        "permit_status": "Permit Issued", "borough": "Brooklyn",
        "bin": BID, "bbl": BBL,
        **overrides,
    }


def filing(**overrides):
    return {
        "job_filing_number": JOB,
        "filing_date": "2025-05-08T00:00:00.000",
        "first_permit_date": "2026-10-16T00:00:00.000",
        "filing_status": "Permit Entire", "job_type": "Alteration",
        "borough": "Brooklyn", "bin": BID, "bbl": BBL,
        "solar_work_type_": "NO",
        "general_construction_work_type_": "YES",
        **overrides,
    }


class DummyResponse:
    def __init__(self, rows):
        self.content = json.dumps(rows).encode("utf-8")

    def raise_for_status(self):
        pass


class FakeOpenData:
    def __init__(self, permits=None, filings=None):
        self.permits = [permit()] if permits is None else permits
        self.filings = [filing()] if filings is None else filings
        self.urls = []
        self.parameters = []

    def get(self, url, *, params, timeout, headers):
        assert timeout <= 15
        assert headers["Accept"] == "application/json"
        self.urls.append(url)
        self.parameters.append(params)
        if url == PERMITS_URL:
            assert "Initial Permit" in params["$where"]
            assert "owner" not in params["$select"] and "address" not in params["$select"]
            return DummyResponse(self.permits)
        assert url == FILINGS_URL
        assert "job_filing_number in" in params["$where"]
        assert "owner" not in params["$select"]
        return DummyResponse(self.filings)


@pytest.fixture()
def bounded(monkeypatch,tmp_path):
    root=tmp_path/"runtime/acquisition"
    root.mkdir(parents=True)
    monkeypatch.setattr(signal_inbox,"ROOT",root)
    monkeypatch.setattr(signal_inbox,"INBOX",root/"signal_inbox.json")
    monkeypatch.setattr(signal_inbox,"LOCK",root/"signal_inbox.lock")
    # Test observation clock must not depend on live production wall time.
    monkeypatch.setattr(signal_inbox,"_now",
                        lambda: (NOW-timedelta(seconds=15)).isoformat())
    return root


def test_valid_first_issuance_joins_real_dates_and_signal_boundary(bounded):
    fake=FakeOpenData()
    d=current_event_sample(now=NOW,client=fake)
    assert len(d["events"])==1
    assert fake.urls==[PERMITS_URL,FILINGS_URL]
    assert d["events"][0]["filing_date"]=="2025-05-08"
    assert d["events"][0]["issued_date"]=="2026-10-16"
    assert d["events"][0]["official_event_crosscheck"] is True
    cand=list(to_signal_candidates(d))[0]
    assert cand.source==SOURCE and not cand.phone and not cand.email
    assert cand.niche=="general_contractor"
    assert assess_candidate(cand).source_role=="signal"
    assert assess_candidate(cand).accepted is False
    res=signal_inbox.enqueue_signal(cand)
    assert res["decision"]=="created"
    row=next(iter(json.loads((bounded/"signal_inbox.json").read_text()).values()))
    assert row["raw"]["issued_date"]=="2026-10-16"
    assert row["raw"]["job_filing_number"]==JOB
    assert row["execution_authority"]=="none"
    assert row["prospect_id"] is None
    assert candidate_from_signal(row,now=NOW)==(
        None,"dobnow_source_event_never_confers_company_identity"
    )
    all_text=json.dumps(row)
    assert "private.owner@" not in all_text and "permittee" not in all_text
    assert "2025-05-08" in all_text


def test_duplicate_reobservation_does_not_create_new_source_event(bounded):
    cand=list(to_signal_candidates(current_event_sample(now=NOW,client=FakeOpenData())))[0]
    a=signal_inbox.enqueue_signal(cand)
    b=signal_inbox.enqueue_signal(cand)
    assert a["signal_id"]==b["signal_id"]
    assert b["decision"]=="matched"
    assert b["source_event_revision_added"] is False
    assert len(json.loads((bounded/"signal_inbox.json").read_text()))==1


def test_signed_new_event_state_updates_same_source_without_identity_change(bounded):
    cand=list(to_signal_candidates(current_event_sample(now=NOW,client=FakeOpenData())))[0]
    signal_inbox.enqueue_signal(cand)
    changed=list(to_signal_candidates(current_event_sample(
        now=NOW,client=FakeOpenData(permits=[permit(work_type="Scaffold")]))))[0]
    result=signal_inbox.enqueue_signal(changed)
    assert result["decision"]=="updated_source_event"
    row=next(iter(json.loads((bounded/"signal_inbox.json").read_text()).values()))
    assert row["raw"]["work_type"]=="Scaffold"
    assert row["source_event_revision_count"]==1
    assert row["source_event_revisions"][0]["company_or_buyer_verified"] is False
    assert len(json.loads((bounded/"signal_inbox.json").read_text()))==1


def test_never_rewind_source_permit_date(bounded):
    row=list(to_signal_candidates(current_event_sample(now=NOW,client=FakeOpenData())))[0]
    signal_inbox.enqueue_signal(row)
    earlier=list(to_signal_candidates(current_event_sample(
        now=NOW,client=FakeOpenData(permits=[
            permit(issued_date="2026-10-15T00:00:00.000")],
            filings=[filing(first_permit_date="2026-10-15T00:00:00.000")]))))[0]
    result=signal_inbox.enqueue_signal(earlier)
    assert result["decision"]=="matched"
    old=next(iter(json.loads((bounded/"signal_inbox.json").read_text()).values()))
    assert old["raw"]["issued_date"]=="2026-10-16"


def test_filing_permit_mismatch_disqualifies_and_never_exports_name():
    cases=[
      FakeOpenData(filings=[filing(bin="9999999")]),
      FakeOpenData(filings=[filing(first_permit_date="2025-10-16T00:00:00.000")]),
      FakeOpenData(permits=[permit(filing_reason="Renewal Permit with Changes")]),
      FakeOpenData(permits=[permit(issued_date="2025-10-16T00:00:00.000")],
                   filings=[filing(first_permit_date="2025-10-16T00:00:00.000")]),
      FakeOpenData(permits=[permit(permit_status="Expired")]),
    ]
    for fake in cases:
        assert current_event_sample(now=NOW,client=fake)["events"]==[]


def test_source_job_id_injection_dropped_before_bounded_filing_query():
    f=FakeOpenData(permits=[permit(job_filing_number="x');DELETE FROM public.x;--")])
    data=current_event_sample(now=NOW,client=f)
    assert data["events"]==[]
    assert f.urls==[PERMITS_URL]


def test_duplicate_work_permit_rows_are_one_project_not_two():
    review = current_event_sample(now=NOW, client=FakeOpenData(
        permits=[permit(), permit(work_type="Scaffold")]
    ))
    assert review["query_rows"] == 2
    assert review["distinct_crosschecked_jobs"] == 1
    assert review["duplicate_work_permit_rows_collapsed"] == 1
    assert review["events"][0]["work_types"] == ["General Construction","Scaffold"]
    assert review["events"][0]["underlying_permit_row_count"] == 2
    with pytest.raises(ValueError,match="SOURCE_RESPONSE_NOT_BOUNDED"):
        current_event_sample(now=NOW,client=FakeOpenData(permits=[permit()]*41))


def test_default_scheduled_source_disabled_even_when_registered(monkeypatch):
    monkeypatch.delenv("EMPIRE_DOBNOW_PERMIT_SOURCE_ENABLED",raising=False)
    _import_sources()
    source=get_source("permits_dobnow")
    assert source.requires==["EMPIRE_DOBNOW_PERMIT_SOURCE_ENABLED"]
    assert list(run(metro="NYC"))==[]
    monkeypatch.setenv("EMPIRE_DOBNOW_PERMIT_SOURCE_ENABLED","false")
    assert list(run(metro="NYC"))==[]
    assert list(run(metro="Chicago"))==[]


def test_incomplete_sample_flag_is_visible():
    rows=[]
    fil=[]
    for i in range(40):
        code=f"B{i:08d}-I1"
        rows.append(permit(job_filing_number=code))
        fil.append(filing(job_filing_number=code))
    x=current_event_sample(now=NOW,client=FakeOpenData(permits=rows,filings=fil))
    assert x["sample_may_be_incomplete"] is True
    assert x["query_rows"]==40
    assert len(x["events"])==40


def test_provider_errors_fail_closed_not_partial():
    class Broken:
        def get(self,*args,**kwargs):raise RuntimeError("API unavailable")
    with pytest.raises(RuntimeError,match="API unavailable"):
        current_event_sample(now=NOW,client=Broken())


def test_pagination_is_bounded_and_cannot_run_unlimited_offsets():
    with pytest.raises(ValueError,match="UNSAFE_PERMIT_PAGE_OFFSET"):
        current_event_sample(now=NOW,offset=1,client=FakeOpenData())
    with pytest.raises(ValueError,match="UNSAFE_PERMIT_PAGE_OFFSET"):
        current_event_sample(now=NOW,offset=400,client=FakeOpenData())
    data=current_event_sample(now=NOW,offset=80,client=FakeOpenData())
    assert data["page_offset"]==80


def test_enabled_source_reuses_existing_crawler_and_stops_after_short_page(monkeypatch):
    import empire_os.lead_sources.nyc_dobnow as mod
    monkeypatch.setenv("EMPIRE_DOBNOW_PERMIT_SOURCE_ENABLED","1")
    offsets=[]
    real=mod.current_event_sample
    def fetched(*,offset=0):
        offsets.append(offset)
        return real(now=NOW,offset=offset,client=FakeOpenData())
    monkeypatch.setattr(mod,"current_event_sample",fetched)
    assert len(list(mod.run(metro="NYC")))==1
    assert offsets==[0]


def test_enabled_multi_page_overlapping_jobs_not_double_counted(monkeypatch):
    import empire_os.lead_sources.nyc_dobnow as mod
    monkeypatch.setenv("EMPIRE_DOBNOW_PERMIT_SOURCE_ENABLED","1")
    seen=[]
    def fake(*,offset):
        seen.append(offset)
        return {
            "status":"OFFICIAL_BOUNDED_EVENT_CROSSCHECK",
            "mode":"OBSERVE","no_sales_authority":True,
            "query_rows":40 if offset<80 else 2,
            "events":[{"job_filing_number":"B01222111-I1","issued_date":"2026-10-16"}],
        }
    monkeypatch.setattr(mod,"current_event_sample",fake)
    assert len(list(mod.run(metro="NYC")))==1
    assert seen==[0,40,80]


def test_dobnow_flows_into_existing_permit_and_property_department_views(bounded):
    from empire_os.permit_project_intelligence import analyze_permit_project_intelligence
    from empire_os.source_intelligence_handoff import build_source_intelligence_handoffs
    from empire_os.permit_intelligence_runtime import build_permit_intelligence_runtime

    root=bounded.parents[1]
    c=list(to_signal_candidates(current_event_sample(
        now=NOW,client=FakeOpenData())))[0]
    signal_inbox.enqueue_signal(c)
    projection=build_permit_intelligence_runtime(root)
    assert projection["by_source"] == {SOURCE:1}
    assert projection["with_raw_reference"]==1
    detailed=analyze_permit_project_intelligence(root,now=NOW)
    assert detailed["cohort"]["recent_original_filing_or_issuance"]==1
    assert detailed["cohort"]["untrusted_or_missing_date"]==0
    dossier=detailed["review_dossiers"][0]
    assert dossier["source_kind"]=="NYC_DOBNOW_TWO_OFFICIAL_DATASET_EVENT"
    assert dossier["project_ref"]=="nyc_dobnow_job:"+JOB
    assert dossier["original_filing_date"]=="2025-05-08"
    assert dossier["original_issuance_date"]=="2026-10-16"
    assert dossier["property_reference"]["bbl"]==BBL
    assert dossier["buyer_demand_proven"] is False
    assert dossier["route"]["external_contact_authorized"] is False
    dispatch=build_source_intelligence_handoffs(root,now=NOW)
    routes={r["lane"]:r for r in dispatch["routes"]}
    assert dispatch["unique_underlying_nyc_permit_signal_count"]==1
    assert routes["permit"]["counts"]["newly_imported_actual_filing_or_issuance_last_30d"]==1
    assert routes["property"]["counts"]["recent_actual_filing_or_issuance_unverified"]==1
    assert routes["permit"]["sale_or_revenue_proven"] is False
    assert "DOB NOW Permit" not in json.dumps(dispatch)


def test_existing_baseline_old_bis_job_namespace_does_not_conflict(bounded):
    from empire_os.permit_project_intelligence import analyze_permit_project_intelligence
    dob=list(to_signal_candidates(current_event_sample(now=NOW,client=FakeOpenData())))[0]
    assert "a810-biswebportal" not in dob.url
    new=signal_inbox.enqueue_signal(dob)
    legacy={
        "source":"permits_nyc",
        "name":"NYC Permit 123456789",
        "niche":"general_contractor","metro":"NYC","state":"NY",
        "url":"https://a810-biswebportal.nyc.gov/bisweb/PropertyOverflowDetails.jsp?job=123456789",
        "raw":{"job__":"123456789","filing_date":"05/08/2025",
               "issuance_date":"10/16/2026","permit_status":"ISSUED",
               "dobrundate":"2026-10-18T00:00:00.000","bbl":"3002697501"}
    }
    old=signal_inbox.enqueue_signal(legacy)
    assert new["signal_id"]!=old["signal_id"]
    assert len(json.loads((bounded/"signal_inbox.json").read_text()))==2
    rows=analyze_permit_project_intelligence(bounded.parents[1],now=NOW)
    assert rows["cohort"]["recent_original_filing_or_issuance"]==2


def test_bounded_batch_writes_one_private_file_not_one_per_signal(bounded):
    from empire_os.signal_inbox import enqueue_signals_batch
    from empire_os.candidate_quality import assess_candidate
    from empire_os.lead_sources import LeadCandidate

    one=list(to_signal_candidates(current_event_sample(
        now=NOW,client=FakeOpenData())))[0]
    batch=[]
    for i in range(150):
        entry=LeadCandidate(**{**one.__dict__,
            "name":f"NYC DOB NOW Permit B{i:08d}-I1",
            "raw":{**one.raw,"job_filing_number":f"B{i:08d}-I1"}})
        batch.append(entry)
    accepted=enqueue_signals_batch(batch,qualities=[assess_candidate(x) for x in batch])
    assert len(accepted)==150
    assert {x["decision"] for x in accepted}=={"created"}
    assert (bounded/"signal_inbox.json").stat().st_mode & 0o777 == 0o600
    matched=enqueue_signals_batch(batch)
    assert {x["decision"] for x in matched}=={"matched"}
    rows=json.loads((bounded/"signal_inbox.json").read_text())
    assert len(rows)==150
    assert all(x["prospect_id"] is None for x in rows.values())


def test_batch_corrupt_existing_inbox_fails_closed_and_preserves_content(bounded):
    from empire_os.signal_inbox import enqueue_signals_batch
    p=bounded/"signal_inbox.json"
    p.write_text("{corrupt existing customer source")
    original=p.read_bytes()
    c=list(to_signal_candidates(current_event_sample(
        now=NOW,client=FakeOpenData())))[0]
    with pytest.raises(ValueError):
        enqueue_signals_batch([c])
    assert p.read_bytes()==original


def test_batch_rejects_mixed_source_or_oversized_payload(bounded):
    from empire_os.signal_inbox import enqueue_signals_batch
    c=list(to_signal_candidates(current_event_sample(
        now=NOW,client=FakeOpenData())))[0]
    with pytest.raises(ValueError,match="BATCH_LIMITED_TO_DOBNOW_SOURCE_EVENTS"):
        enqueue_signals_batch([c,{"source":"courtlistener","name":"unknown"}])
    with pytest.raises(ValueError,match="UNBOUNDED_SIGNAL_BATCH"):
        enqueue_signals_batch([c]*401)
    assert not (bounded/"signal_inbox.json").exists()


def test_existing_crawler_uses_one_dobnow_batch_without_db(bounded, monkeypatch):
    from empire_os.crawler_runner import run_source_safe
    from empire_os.lead_sources import LeadCandidate, SourceInfo
    from empire_os.lead_sources.nyc_dobnow import to_signal_candidates
    one=list(to_signal_candidates(current_event_sample(
        now=NOW,client=FakeOpenData())))[0]
    def candidates(metro):
        for i in range(60):
            yield LeadCandidate(**{**one.__dict__,
              "name":f"NYC DOB NOW Permit B{i:08d}-I1",
              "raw":{**one.raw,"job_filing_number":f"B{i:08d}-I1"}})
    src=SourceInfo(name="permits_dobnow",tier="real",requires=[],
                   description="test",run_fn=candidates)
    monkeypatch.setattr("empire_os.crawler_runner.log",lambda *a,**kw:None)
    observed,accepted,errors=run_source_safe(src,"NYC",dry_run=False)
    assert (observed,accepted,errors)==(60,60,0)
    assert len(json.loads((bounded/"signal_inbox.json").read_text()))==60
    observed,accepted,errors=run_source_safe(src,"NYC",dry_run=False)
    assert (observed,accepted,errors)==(60,60,0)
    assert len(json.loads((bounded/"signal_inbox.json").read_text()))==60
    assert all(r["prospect_id"] is None for r in
               json.loads((bounded/"signal_inbox.json").read_text()).values())
