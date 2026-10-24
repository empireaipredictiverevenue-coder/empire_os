"""Deadline review never promotes official tenders into bid/contact authority."""
from datetime import datetime,timedelta,timezone
from copy import deepcopy
import json
import os

from scripts.review_official_tender_founder_deadlines_20261024 import (
    READY_STATUS,HOLD_STATUS,triage,review_existing_report,save_private_result,OUTPUT,
)
from empire_os.gtm_procurement_research_source import SCHEMA,REPORT

NOW=datetime(2026,10,24,10,0,tzinfo=timezone.utc)
OBS=NOW-timedelta(minutes=15)


def packet():
    source={
        "source":"contracts_finder",
        "ocid":"ocds-b5fd17-abc123",
        "buyer_organisation":"Example Council",
        "title":"GDPR Data Audit",
        "notice_url":"https://www.contractsfinder.service.gov.uk/Notice/5f4d9841-b30a-42bb-b122-3f7758606443",
        "notice_release_at":(NOW-timedelta(days=3)).isoformat(),
        "tender_closes_at":(NOW+timedelta(hours=60)).isoformat(),
        "request_status":"PUBLIC_TENDER_OPEN_AS_OF_OBSERVATION",
        "review_status":"CUSTOM_SCOPE_NO_VERIFIED_PRODUCT_FIT",
        "candidate_product_code":None,
        "external_purchasing_requirement_evidence":True,
        "bid_eligibility_verified":False,
        "tender_documents_reviewed":False,
        "product_fit_verified":False,
        "contact_permission_cleared":False,
        "suppression_checked":False,
        "outbound_authorized":False,
        "buyer_interest_in_empire_ai_verified":False,
    }
    return {
        "schema_version":SCHEMA,"mode":"OBSERVE",
        "releases_inspected":1,"open_service_requirements_identified":1,
        "product_hypotheses":0,"records":[source],
        "observed_at":OBS.isoformat(),
        "canonical_qualified":0,"crm_writes":False,"outbound_authorized":False,
        "model_training_authorized":False,"verified_revenue":None,
        "external_bid_submitted":False,"verified_customer_inquiry":False,
    }


def test_near_deadline_is_urgent_review_never_bid_ready():
    result=triage(packet(),now=NOW)
    assert result["status"]==READY_STATUS
    assert result["due_within_72_hours_count"]==1
    assert result["bid_ready_count"]==0
    assert result["source_qualified_customer_count"]==0
    assert result["bid_submissions"]==0
    assert result["external_bids_authorized"] is False
    assert result["crm_writes"] is False
    assert result["outbound_sent"] is False
    row=result["items"][0]
    assert row["deadline_urgency"]=="DUE_WITHIN_72_HOURS"
    assert row["policy_or_supplier_hold"]=="HOLD_CUSTOM_SCOPE_OR_SUPPLIER_FIT"
    assert row["individual_document_and_amendment_recheck_required"] is True
    assert row["bid_authorized"] is False


def test_no_paid_traffic_notice_remains_held():
    p=packet()
    p["records"][0]["review_status"]="NO_PAID_TRAFFIC_POLICY_HOLD"
    out=triage(p,now=NOW)
    assert out["status"]==READY_STATUS
    assert out["paid_traffic_or_scope_hold_count"]==1
    assert out["items"][0]["policy_or_supplier_hold"]=="HOLD_PAID_TRAFFIC_OR_UNCLEAR_PAID_SCOPE"
    assert out["external_bids_authorized"] is False


def test_closed_since_scan_cannot_be_classified_as_open():
    p=packet()
    p["records"][0]["tender_closes_at"]=(NOW-timedelta(minutes=4)).isoformat()
    r=triage(p,now=NOW)
    assert r["status"]==READY_STATUS
    assert r["closed_after_snapshot_count"]==1
    assert r["items"][0]["required_next_action"]=="DO_NOT_BID_CLOSED_NOTICE"


def test_stale_snapshot_and_tampering_fail_closed():
    p=packet()
    cases=[]
    stale=deepcopy(p); stale["observed_at"]=(NOW-timedelta(hours=25)).isoformat();cases.append(stale)
    fake=deepcopy(p);fake["records"][0]["bid_eligibility_verified"]=True;cases.append(fake)
    marketing=deepcopy(p);marketing["records"][0]["contact_permission_cleared"]=True;cases.append(marketing)
    forged=deepcopy(p);forged["records"][0]["notice_url"]="https://evil.test/Notice/test";cases.append(forged)
    changed=deepcopy(p);changed["records"][0]["notice_url"]="https://www.contractsfinder.service.gov.uk/Notice/5f4d9841-b30a-42bb-b122-3f7758606443?token=a";cases.append(changed)
    undated=deepcopy(p);undated["records"][0]["tender_closes_at"]="not-a-date";cases.append(undated)
    old=deepcopy(p);old["records"][0]["tender_closes_at"]=(OBS-timedelta(hours=1)).isoformat();cases.append(old)
    duplicate=deepcopy(p);duplicate["records"].append(deepcopy(duplicate["records"][0]));duplicate["open_service_requirements_identified"]=2;duplicate["releases_inspected"]=2;cases.append(duplicate)
    for candidate in cases:
        out=triage(candidate,now=NOW)
        assert out["status"]==HOLD_STATUS
        assert "items" not in out
        assert out["bid_ready_count"]==0
        assert out["outbound_sent"] is False


def test_private_receipt_permissions_and_symlink_denial(tmp_path):
    p=packet()
    folder=tmp_path/OUTPUT.parent
    folder.mkdir(parents=True)
    report=triage(p,now=NOW)
    save_private_result(tmp_path, report)
    target=tmp_path/OUTPUT
    assert target.stat().st_mode & 0o077 == 0
    assert json.loads(target.read_text())["items"][0]["bid_authorized"] is False
    source=tmp_path/REPORT
    source.write_text(json.dumps(p),encoding="utf-8")
    source.chmod(0o600)
    assert review_existing_report(tmp_path,now=NOW)["status"]==READY_STATUS
    source.chmod(0o644)
    assert review_existing_report(tmp_path,now=NOW)["status"]==HOLD_STATUS
    target.unlink()
    outside=tmp_path/"outside"
    outside.write_text("remain",encoding="utf-8")
    target.symlink_to(outside)
    try:
        save_private_result(tmp_path,report)
        assert False,"symlink target should fail"
    except ValueError:
        pass
    assert outside.read_text()=="remain"
