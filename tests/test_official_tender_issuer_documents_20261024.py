"""Original official tender issuer-document manifests are references, never proof."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import pytest

from empire_os.data_exchange_procurement_context import OGL_V3
from scripts.review_official_tender_issuer_documents_20261024 import (
    READY, HELD, OUT, enumerate_issuer_references, write_private, observe,
)

NOW=datetime(2026,10,24,10,0,tzinfo=timezone.utc)
OCID="ocds-b5fd17-4f1d763a-8ba8-4b2c-9b97-6ea1e7ab3a42"
NOTICE="https://www.contractsfinder.service.gov.uk/Notice/5f4d9841-b30a-42bb-b122-3f7758606443"
DOC="https://www.contractsfinder.service.gov.uk/Notice/Attachment/abdbaec1-6b85-4b3f-9dfe-963b78925c5f"
DEADLINE="2026-10-26T12:00:00+00:00"


def target():
    return {
        "source":"contracts_finder","ocid":OCID,
        "policy_or_supplier_hold":"HOLD_CUSTOM_SCOPE_OR_SUPPLIER_FIT",
        "deadline_urgency":"DUE_WITHIN_72_HOURS",
        "official_notice_url":NOTICE,
        "title":"GDPR Data Audit","tender_closes_at_utc":DEADLINE,
    }


def release(*,amendment=True):
    return {
        "id":"5f4d9841-b30a-42bb-b122-3f7758606443-918510",
        "ocid":OCID,
        "date":"2026-10-21T09:08:47+01:00",
        "tag":["tenderAmendment" if amendment else "tender"],
        "tender":{
            "status":"active","title":"GDPR Data Audit",
            "tenderPeriod":{"endDate":DEADLINE},
            "documents":[
                {"documentType":"tenderNotice","url":NOTICE,"format":"text/html"},
                {"documentType":"biddingDocuments","url":DOC,"format":"application/pdf"},
            ],
        },
    }


def packet(*items):
    return {
        "publisher":{"name":"Cabinet Office"},
        "license":OGL_V3,
        "releases":list(items),
    }


def test_recent_amendment_captured_without_fake_attachment_access():
    data=enumerate_issuer_references([packet(release())],[target()],observed_at=NOW)
    assert data["status"]==READY
    assert data["target_notices"]==1
    assert data["document_references"]==2
    assert data["issuer_amendment_references"]==1
    item=data["items"][0]
    assert item["release_versions_seen"]==1
    assert item["document_access"]=="REFERENCES_ONLY_CONTENT_NOT_VERIFIED"
    assert item["original_attachments_restricted_or_unread"] is True
    assert item["bid_eligibility_verified"] is False
    assert all(not x["content_retrieved"] for x in item["issuer_documents"])
    assert all(not x["content_hash_verified"] for x in item["issuer_documents"])
    assert data["external_bid_sent"] is False
    assert data["outbound_sent"] is False
    assert data["crm_writes"] is False


def test_versions_stay_deduplicated_at_latest_amendment():
    before=release(amendment=False)
    before["date"]="2026-10-07T13:13:58+01:00"
    before["tender"]["documents"]=before["tender"]["documents"][:1]
    data=enumerate_issuer_references(
        [packet(before),packet(release())],[target()],observed_at=NOW,
    )
    assert data["status"]==READY
    assert data["document_references"]==2
    assert data["items"][0]["release_versions_seen"]==2
    assert data["issuer_amendment_references"]==1


@pytest.mark.parametrize("change", [
    "wrong_licence","wrong_issuer","future","duplicate_docs",
    "off_origin","non_utc_deadline","unknown_document","wrong_title",
    "wrong_deadline","missing_notice","unapproved_policy",
])
def test_untrusted_document_meta_denied(change):
    t=target()
    p=packet(release())
    if change=="wrong_licence":p["license"]="unlicensed"
    elif change=="wrong_issuer":p["publisher"]["name"]="Unknown"
    elif change=="future":p["releases"][0]["date"]=(NOW+timedelta(minutes=2)).isoformat()
    elif change=="duplicate_docs":p["releases"][0]["tender"]["documents"].append(p["releases"][0]["tender"]["documents"][0].copy())
    elif change=="off_origin":p["releases"][0]["tender"]["documents"][1]["url"]="https://example.com/file"
    elif change=="non_utc_deadline":p["releases"][0]["tender"]["tenderPeriod"]["endDate"]="2026-10-26T13:00:00"
    elif change=="unknown_document":p["releases"][0]["tender"]["documents"][1]["documentType"]="unknown"
    elif change=="wrong_title":p["releases"][0]["tender"]["title"]="Something different"
    elif change=="wrong_deadline":p["releases"][0]["tender"]["tenderPeriod"]["endDate"]="2026-11-12T12:00:00Z"
    elif change=="missing_notice":p["releases"][0]["tender"]["documents"].pop(0)
    elif change=="unapproved_policy":t["policy_or_supplier_hold"]="HOLD_PAID_TRAFFIC_OR_UNCLEAR_PAID_SCOPE"
    data=enumerate_issuer_references([p],[t],observed_at=NOW)
    assert data["status"]==HELD
    assert "items" not in data
    assert data["supplier_eligible_count"]==0
    assert data["document_content_verified_count"]==0
    assert data["external_bid_sent"] is False


def test_private_index_write_is_read_only_metadata(tmp_path):
    report=enumerate_issuer_references([packet(release())],[target()],observed_at=NOW)
    folder=tmp_path/OUT.parent
    folder.mkdir(parents=True)
    folder.chmod(0o700)
    path=write_private(tmp_path,report)
    assert path.stat().st_mode & 0o077 == 0
    assert json.loads(path.read_text())["items"][0]["bid_eligibility_verified"] is False
    path.unlink()
    outside=tmp_path/"outside"
    outside.write_text("untouched")
    path.symlink_to(outside)
    with pytest.raises(ValueError):
        write_private(tmp_path,report)
    assert outside.read_text()=="untouched"
    with pytest.raises(ValueError):
        write_private(tmp_path,enumerate_issuer_references([],[],observed_at=NOW))


def test_missing_original_deadline_snapshot_cannot_fetch_or_approve(tmp_path):
    result=observe(tmp_path,now=NOW,fetch=lambda url: (_ for _ in ()).throw(AssertionError("should not fetch")))
    assert result["status"]==HELD
    assert result["external_bid_sent"] is False
