"""Fail-closed source-owner automation tests; never call external sources."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
import pytest

from empire_os import data_brokerage_texas_agent as agent
from scripts.verify_texas_construction_paid_trial_source_20261117 import (
    assess, where_for_month,
)

NOW=datetime(2026,11,17,20,50,tzinfo=timezone.utc)
HASH="a"*64

def dallas(rows=None, *, now=NOW):
    if rows is None:
        rows=[{
            "permit_number":"COM-NEW-26-000372",
            "issued_date":"11/10/26",
            "permit_type":"Commercial New Construction Permit",
            "work_description":"New hotel shell",
        }]
    return assess(rows,now=now,total=len(rows),
                  sample_sha=HASH,count_sha=HASH,month=now.strftime("%Y-%m"))

def fort():
    return {
        "status":"FORT_WORTH_STATUS_UPDATE_SAMPLE_NOT_NEW_ISSUANCES",
        "source_url":agent.FW_URL,
        "source_response_sha256":HASH,
        "month":"2026-11",
        "source_rows_sampled":3,
        "source_rows_accepted_after_quarantine":2,
        "source_future_or_invalid_rows_quarantined":1,
        "distinct_permits_in_sample":1,
        "duplicate_permit_rows":1,
        "sample_may_be_incomplete":False,
        "original_issue_date_verified":False,
        "status_changed_dates":{"2026-11-16":2},
        "original_filing_year_counts":{"2024":1,"2026":1},
        "commercial_permit_types":{"Commercial Grading Permit":2},
        "named_people_or_property_addresses_saved":False,
        "company_buying_intent_verified":False,
        "customer_delivery_enabled":False,
    }

class Response:
    status_code=200
    headers={"Content-Type":"application/json; charset=utf-8"}
    def __init__(self,features):
        self.content=json.dumps({"features":features,
            "exceededTransferLimit":False}).encode()

def millis(s):
    return int(datetime.strptime(s,"%Y-%m-%d").replace(
        tzinfo=timezone.utc).timestamp()*1000)

def source_rows():
    good={
        "Permit_No":"CG26-00123","Permit_Type":"Commercial Grading Permit",
        "Current_Status":"Issued","Status_Date":millis("2026-11-16"),
        "File_Date":millis("2024-07-09"),
        "Use_Type":None,"Specific_Use":None,
    }
    future={**good,"Permit_No":"CG26-00999",
        "Status_Date":millis("2026-12-01")}
    return [{"attributes":good},{"attributes":dict(good)},{"attributes":future}]

def test_fortworth_quarantines_future_and_deduplicates_status_rows():
    calls=[]
    def get(url,params,**kwargs):
        calls.append((url,params,kwargs))
        return Response(source_rows())
    x=agent.read_fortworth_month(now=NOW,request_get=get)
    assert x["source_rows_sampled"]==3
    assert x["source_rows_accepted_after_quarantine"]==2
    assert x["source_future_or_invalid_rows_quarantined"]==1
    assert x["distinct_permits_in_sample"]==1
    assert x["duplicate_permit_rows"]==1
    assert x["original_issue_date_verified"] is False
    assert calls[0][1]["returnGeometry"]=="false"
    assert "Owner_Full_Name" not in calls[0][1]["outFields"]

def test_fortworth_source_hold_when_all_rows_invalid():
    def get(url,params,**kwargs):
        return Response([source_rows()[-1]])
    with pytest.raises(ValueError,match="TOO_MANY"):
        agent.read_fortworth_month(now=NOW,request_get=get)

def test_original_owner_private_state_automatic_cycle(tmp_path, monkeypatch):
    monkeypatch.setattr(agent,"CANONICAL",tmp_path.resolve())
    r=agent.run_texas_research(
        tmp_path,now=NOW,persist=True,dallas_reader=dallas,
        fortworth_reader=fort,
    )
    assert r["status"]=="TEXAS_AGENT_DALLAS_AND_FORT_WORTH_RESEARCH_VERIFIED"
    assert r["source_receipts_committed"] is True
    path=tmp_path/agent.STATE
    assert path.exists() and os.stat(path).st_mode & 0o077==0
    saved=agent.load_state(tmp_path,now=NOW)
    assert saved and saved["dallas"]["rows_accepted"]==1
    assert saved["fort_worth"]["source_future_or_invalid_rows_quarantined"]==1
    assert saved["buyer_fit"]["pilot_ready"] is False
    assert saved["dallas_change_since_prior_valid_cycle"]["newly_observed_keyword_permit_refs"]==0
    r2=agent.run_texas_research(
        tmp_path,now=NOW+timedelta(hours=12),persist=True,
        dallas_reader=lambda:dallas(now=NOW+timedelta(hours=12)),
        fortworth_reader=fort,
    )
    assert r2["newly_observed_keyword_ref_changes"]==0
    assert agent.load_state(tmp_path,now=NOW+timedelta(hours=12))

def test_new_source_candidate_delta_is_not_qualified_buyer(tmp_path,monkeypatch):
    monkeypatch.setattr(agent,"CANONICAL",tmp_path.resolve())
    agent.run_texas_research(
        tmp_path,now=NOW,persist=True,dallas_reader=dallas,fortworth_reader=fort,
    )
    rows=[{
        "permit_number":"COM-NEW-26-000372",
        "issued_date":"11/10/26",
        "permit_type":"Commercial New Construction Permit",
        "work_description":"Hotel shell",
    },{
        "permit_number":"COM-NEW-26-000149",
        "issued_date":"11/16/26",
        "permit_type":"Commercial New Construction Permit",
        "work_description":"New multifamily construction",
    }]
    r=agent.run_texas_research(
        tmp_path,now=NOW+timedelta(hours=12),persist=True,
        dallas_reader=lambda:dallas(rows,now=NOW+timedelta(hours=12)),
        fortworth_reader=fort,
    )
    assert r["newly_observed_keyword_ref_changes"]==1
    assert r["buyer_fulfilment_ready"] is False
    assert r["outreach_sent"] is False
    snapshot=agent.load_state(tmp_path,now=NOW+timedelta(hours=12))
    assert snapshot["buyer_qualified"] is False

def test_failed_primary_source_preserves_last_good_receipt(tmp_path,monkeypatch):
    monkeypatch.setattr(agent,"CANONICAL",tmp_path.resolve())
    agent.run_texas_research(tmp_path,now=NOW,persist=True,
        dallas_reader=dallas,fortworth_reader=fort)
    before=(tmp_path/agent.STATE).read_bytes()
    def unavailable():
        raise ValueError("source timeout")
    r=agent.run_texas_research(tmp_path,now=NOW+timedelta(hours=12),
        persist=True,dallas_reader=unavailable,fortworth_reader=fort)
    assert r["status"]=="DALLAS_OFFICIAL_SOURCE_HOLD"
    assert r["source_receipts_committed"] is False
    assert (tmp_path/agent.STATE).read_bytes()==before

def test_partial_fortworth_holder_does_not_fake_new_issuances(tmp_path,monkeypatch):
    monkeypatch.setattr(agent,"CANONICAL",tmp_path.resolve())
    def fail():
        raise TimeoutError()
    r=agent.run_texas_research(tmp_path,now=NOW,persist=True,
        dallas_reader=dallas,fortworth_reader=fail)
    assert r["status"]=="TEXAS_AGENT_DALLAS_VERIFIED_FORT_WORTH_HELD"
    saved=agent.load_state(tmp_path,now=NOW)
    assert saved and saved["fort_worth"]["status"]=="FORT_WORTH_OFFICIAL_SOURCE_HOLD"

@pytest.mark.parametrize("bad",[
    ("customer_delivery_enabled",True),
    ("outbound_sent",True),
])
def test_elevated_authority_rejected_in_private_source_state(tmp_path,monkeypatch,bad):
    monkeypatch.setattr(agent,"CANONICAL",tmp_path.resolve())
    agent.run_texas_research(tmp_path,now=NOW,persist=True,
        dallas_reader=dallas,fortworth_reader=fort)
    payload=agent.load_state(tmp_path,now=NOW)
    payload.pop("integrity_sha256")
    payload[bad[0]]=bad[1]
    assert not agent.validate_state(payload,now=NOW)

def test_raw_contact_field_injection_rejected(tmp_path,monkeypatch):
    monkeypatch.setattr(agent,"CANONICAL",tmp_path.resolve())
    agent.run_texas_research(tmp_path,now=NOW,persist=True,
        dallas_reader=dallas,fortworth_reader=fort)
    value=agent.load_state(tmp_path,now=NOW)
    value.pop("integrity_sha256")
    value["dallas"]["owner_email"]="someone@example.com"
    assert not agent.validate_state(value,now=NOW)
    value["dallas"].pop("owner_email")
    value["fort_worth"]["owner_name"]="Unverified"
    assert not agent.validate_state(value,now=NOW)

def test_tampering_invalidates_sha_and_snapshot_expiry(tmp_path,monkeypatch):
    monkeypatch.setattr(agent,"CANONICAL",tmp_path.resolve())
    agent.run_texas_research(tmp_path,now=NOW,persist=True,
        dallas_reader=dallas,fortworth_reader=fort)
    assert agent.load_state(tmp_path,now=NOW+timedelta(hours=41)) is None
    file=tmp_path/agent.STATE
    data=json.loads(file.read_text())
    data["buyer_qualified"]=True
    file.write_text(json.dumps(data))
    assert agent.load_state(tmp_path,now=NOW) is None

def test_next_month_query_rolls_without_hardcoded_2026_november():
    assert where_for_month("2026-12")=="issued_date like '12/%/26' and permit_type = 'Commercial New Construction Permit'"
    rows=[{
        "permit_number":"COM-NEW-26-005555","issued_date":"12/02/26",
        "permit_type":"Commercial New Construction Permit",
        "work_description":"Commercial office shell",
    }]
    x=dallas(rows,now=datetime(2026,12,5,tzinfo=timezone.utc))
    assert x["period"]=="2026-12"
    assert x["rows_accepted"]==1

def test_fortworth_extreme_future_timestamp_is_quarantined():
    accepted = source_rows()[0]
    dangerous = {
        **accepted["attributes"],
        "Permit_No":"CG26-OVERFLOW",
        "Status_Date":10**90,
    }
    def get(url,params,**kwargs):
        return Response([accepted,{"attributes":dangerous}])
    x=agent.read_fortworth_month(now=NOW,request_get=get)
    assert x["source_rows_sampled"]==2
    assert x["source_rows_accepted_after_quarantine"]==1
    assert x["source_future_or_invalid_rows_quarantined"]==1
    assert x["original_issue_date_verified"] is False


def test_only_genuine_existing_owner_trigger_may_be_marked_automated(tmp_path,monkeypatch):
    monkeypatch.setattr(agent,"CANONICAL",tmp_path.resolve())
    with pytest.raises(ValueError,match="OWNER_OR_CLOCK"):
        agent.run_texas_research(
            tmp_path,now=NOW,persist=True,
            trigger="FAKE_SCHEDULED",
            dallas_reader=dallas,fortworth_reader=fort,
        )
    result=agent.run_texas_research(
        tmp_path,now=NOW,persist=True,
        trigger="ORIGINAL_BROKERAGE_CYCLE",
        dallas_reader=dallas,fortworth_reader=fort,
    )
    assert result["execution_trigger"]=="ORIGINAL_BROKERAGE_CYCLE"
    saved=agent.load_state(tmp_path,now=NOW)
    assert saved["execution_trigger"]=="ORIGINAL_BROKERAGE_CYCLE"
