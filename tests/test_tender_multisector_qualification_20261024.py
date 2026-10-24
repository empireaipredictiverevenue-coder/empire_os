"""Fail-closed multi-sector original procurement portfolio unit tests."""
from __future__ import annotations
from datetime import datetime,timezone,timedelta
import copy
import json
import os
from pathlib import Path
import stat
import pytest
from empire_os import tender_multisector_qualification_20261024 as m

NOW=datetime(2026,10,24,17,0,tzinfo=timezone.utc)


def baseline():
    rows=[]
    for i,sector in enumerate(m.CAPABILITY_GATES):
        ocid="ocds-h6vhtk-"+format(10+i,"06x")
        rows.append({
            "ocid":ocid,
            "notice_title":"Synthetic fixture "+sector,
            "sector":sector,"record_api_url":m.FTS+ocid,
            "empire_ai_bid_submitted":False,"external_outreach_authorised":False,
            "paid_buyer_order_verified":False,"stage":"active" if i<6 else "planned",
        })
    return {
        "schema_version":"empire.cross_sector_official_deals_research.v1",
        "verification":"PUBLIC_OCDS_API_READ_ONLY_VERIFIED_EACH_RECORD",
        "canonical_empiredb_writes":False,"contact_emails_sent":False,
        "formal_submissions":0,"actual_fees_earned_gbp":0,
        "discovery_evidence_count":len(rows),"opportunities":rows,
    }


def official_for(row):
    status=row["stage"]
    return {
        "license":m.OGL_V3,
        "publisher":{"name":"Cabinet Office"},
        "records":[{
            "ocid":row["ocid"],
            "releases":[{"id":"100567-2026"}],
            "compiledRelease":{
                "date":"2026-10-23T09:00:00Z",
                "buyer":{"name":"Fixture Public Buyer"},
                "tender":{
                    "title":row["notice_title"],"status":status,
                    "value":{"amount":25000,"currency":"GBP"},
                    "tenderPeriod":{"endDate":"2026-11-05T12:00:00Z"} if status=="active" else {},
                    "enquiryPeriod":{"endDate":"2026-10-28T12:00:00Z"} if status=="active" else {},
                },
            }
        }]
    }


def fake_page(key):
    c=m.CHALLENGES[key]
    day="06/11/2026" if key=="446" else "04/12/2026"
    return (
        "<html><head><title>"+c["title"]+" | Innovate UK Business Connect</title></head>"
        "<body><h1>"+c["title"]+"</h1><h2>Challenge opens</h2>05/10/2026"
        "<h2>Challenge closes</h2>"+day+
        "<p>You must be logged in to see the full information</p>"
        "<p>Read-only synthetic fixture; no actual purchaser.</p>"*18
        +"</body></html>"
    )


def records():
    old=baseline()
    return old,{x["ocid"]:official_for(x) for x in old["opportunities"]},{key:fake_page(key) for key in m.CHALLENGES}


def test_manual_multi_sector_source_truth_and_no_authority():
    original,public,pages=records()
    result=m.qualify(original,public,pages,observed_at=NOW)
    assert result["status"]=="MULTISECTOR_PUBLIC_OPPORTUNITIES_REVIEW_ONLY"
    assert result["public_procurement_cases_verified"]==10
    assert result["innovation_challenge_pages_verified"]==2
    assert result["independent_opportunities_count"]==11
    assert result["distinct_sectors_count"]==11
    assert result["cross_notice_duplicate_dfe_challenge_count"]==1
    assert result["opportunities"][0]["sector"]=="defence_supply_chain_evidence"
    assert result["opportunities"][0]["rank_for_manual_review"]==1
    assert result["opportunities"][0]["challenge_closing_clock_time"]=="UNKNOWN"
    assert all(x["buyer_interest_in_empire_ai_verified"] is False for x in result["opportunities"])
    assert all(x["evidence_backed_platform_workpackage_fit"]=="HYPOTHESIS_ONLY" for x in result["opportunities"])
    assert all(x["complete_customer_deliverable_verified"] is False for x in result["opportunities"])
    assert set(result["opportunities"][0]["candidate_existing_product_components"])=={"entity_graph_export","market_signal_feed"}
    assert all(isinstance(x["candidate_existing_product_components"],list) for x in result["opportunities"])
    assert not result["crm_writes"] and not result["new_emails_sent"] and not result["new_tender_submissions"]
    assert not result["source_data_accepted_to_canonical_empiredb"]
    dfe=[x for x in result["opportunities"] if x["sector"]=="education_built_environment"][0]
    assert dfe["related_innovate_uk_challenge"]==m.CHALLENGE+"447"
    assert dfe["challenge_closing_date"]=="2026-12-04"
    nhs=[x for x in result["opportunities"] if x["sector"]=="healthcare_data"][0]
    assert nhs["tender_submission_deadline_utc"]=="2026-11-05T12:00:00+00:00"
    assert nhs["questions_deadline_utc"]=="2026-10-28T12:00:00+00:00"


@pytest.mark.parametrize("edit",[
    lambda x:x.update(verification="UNVERIFIED"),
    lambda x:x.update(canonical_empiredb_writes=True),
    lambda x:x.update(contact_emails_sent=True),
    lambda x:x.update(formal_submissions=1),
    lambda x:x["opportunities"][0].update(record_api_url="https://malicious.invalid"),
    lambda x:x["opportunities"][0].update(external_outreach_authorised=True),
    lambda x:x["opportunities"][1].update(ocid=x["opportunities"][0]["ocid"]),
    lambda x:x["opportunities"][0].update(sector="unknown_sector"),
])
def test_untrusted_baseline_fails_closed(edit):
    original,public,pages=records()
    edit(original)
    with pytest.raises(ValueError):
        m.qualify(original,public,pages,observed_at=NOW)


@pytest.mark.parametrize("edit",[
    lambda x:x.update(license="not-OGL"),
    lambda x:x.update(publisher={"name":"Untrusted"}),
    lambda x:x["records"][0].update(ocid="ocds-h6vhtk-badbad"),
    lambda x:x["records"][0]["compiledRelease"]["tender"].update(status="awarded"),
    lambda x:x["records"][0]["compiledRelease"]["tender"].update(title="Different notice"),
    lambda x:x["records"][0]["compiledRelease"]["tender"]["value"].update(currency="USD"),
    lambda x:x["records"][0]["compiledRelease"]["tender"].update(value={"amount":-1,"currency":"GBP"}),
])
def test_untrusted_official_feed_or_changed_scope_holds(edit):
    original,public,pages=records()
    p=public[original["opportunities"][0]["ocid"]]
    edit(p)
    with pytest.raises(ValueError):
        m.qualify(original,public,pages,observed_at=NOW)


def test_missing_record_or_challenge_page_holds():
    original,public,pages=records()
    public.pop(next(iter(public)))
    with pytest.raises(ValueError,match="INCOMPLETE"):
        m.qualify(original,public,pages,observed_at=NOW)
    original,public,pages=records()
    pages.pop("446")
    with pytest.raises(ValueError,match="COVERAGE_INCOMPLETE"):
        m.qualify(original,public,pages,observed_at=NOW)


def test_challenge_public_closing_change_blocks_wrong_deadline():
    original,public,pages=records()
    pages["446"]=pages["446"].replace("06/11/2026","03/11/2026")
    with pytest.raises(ValueError,match="DEADLINE_CHANGED"):
        m.qualify(original,public,pages,observed_at=NOW)


def test_nhs_expired_notice_not_represented_as_open():
    original,public,pages=records()
    r=public[original["opportunities"][0]["ocid"]]
    r["records"][0]["compiledRelease"]["tender"]["tenderPeriod"]["endDate"]="2026-10-20T12:00:00Z"
    result=m.qualify(original,public,pages,observed_at=NOW)
    healthcare=[x for x in result["opportunities"] if x["sector"]=="healthcare_data"][0]
    assert healthcare["review_status"]=="SUBMISSION_CLOSED_NO_BID"
    assert healthcare["founder_bid_authority"] is False


def test_private_root_no_automatic_outreach(tmp_path:Path):
    (tmp_path/m.BASE).mkdir(parents=True)
    os.chmod(tmp_path/m.BASE,0o700)
    original,public,pages=records()
    p=tmp_path/m.BASE/m.INPUT
    p.write_text(json.dumps(original))
    os.chmod(p,0o600)
    x=m._read_private(tmp_path)
    assert x["formal_submissions"]==0
    assert m.qualify(x,public,pages,observed_at=NOW)["actual_clients_contracted"]==0
    assert stat.S_IMODE(p.stat().st_mode)==0o600


def test_symlink_source_refused(tmp_path:Path):
    (tmp_path/m.BASE).mkdir(parents=True)
    os.chmod(tmp_path/m.BASE,0o700)
    source=tmp_path/"elsewhere.json"
    source.write_text(json.dumps(baseline()))
    (tmp_path/m.BASE/m.INPUT).symlink_to(source)
    with pytest.raises(ValueError):
        m._read_private(tmp_path)


def test_aware_clock_required():
    old,pub,pages=records()
    with pytest.raises(ValueError):
        m.qualify(old,pub,pages,observed_at=datetime(2026,10,24,18))
