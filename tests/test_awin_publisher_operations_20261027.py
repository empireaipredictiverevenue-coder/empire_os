"""Tests for the existing EmpireOS Awin reviewer; no outbound or account action."""
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import stat
from types import SimpleNamespace

import pytest

from empire_os.awin_publisher_operations import (
    AwinReviewHold, _private_receipt, _atomic_private_write,
    evaluate, scan_awin_candidates, run, SOURCE, OUTPUT, SCHEMA
)

NOW=datetime(2026,10,27,13,20,tzinfo=timezone.utc)


def receipt():
    return {
        "publisher_id":"3136281",
        "publisher_account_approved":True,
        "publisher_account_activated_per_awin_email":True,
        "email_verification_confirmed":False,
        "advertiser_decisions_verified_count":0,
        "advertiser_tracking_links_issued":False,
        "commission_earned_proven":False,
        "commission_received_proven":False,
        "advertiser_programmes":[
            {"advertiser_id":"122556","advertiser":"OVO Solar & Heating",
             "advertiser_acceptance_evidence":False,
             "status":"APPLICATION_SUBMITTED_FOUNDER_REPORTED_AWAITING_ADVERTISER_DECISION"},
            {"advertiser_id":"73922","advertiser":"Glow Green",
             "advertiser_acceptance_evidence":False,
             "status":"APPLICATION_SUBMITTED_FOUNDER_REPORTED_AWAITING_ADVERTISER_DECISION"},
        ],
        "commercial_publication_readiness":{
            "live_affiliate_traffic_authorized":False,
            "owner_handoff_path":"/owner/handoff",
        },
    }


def write_src(root: Path, source=None):
    dest=root/SOURCE
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(source or receipt()))
    dest.chmod(0o600)
    return dest


class Call:
    def __init__(self, data):
        self.data=data
    def execute(self):
        return self.data


class Service:
    def __init__(self, messages=(), extra=None):
        self.mapping={m["id"]:m for m in messages}
        self.extra=extra or {}
        self.requests=[]
    def users(self):
        return self
    def messages(self):
        return self
    def list(self,**kw):
        self.requests.append(("list",kw))
        return Call({"messages":[{"id":x} for x in self.mapping],
                     **self.extra})
    def get(self,**kw):
        self.requests.append(("get",kw))
        return Call(self.mapping[kw["id"]])


def email(id="1234567890abcdef", sender="notices@awin.com",
          subject="Glow Green programme decision", labels=("INBOX",)):
    return {"id":id,"labelIds":list(labels),
            "internalDate":str(int(NOW.timestamp()*1000)),
            "payload":{"headers":[
                {"name":"From","value":sender},
                {"name":"Subject","value":subject},
            ]},
            "body":"NEVER PERSIST SECRET",
            "snippet":"NEVER PERSIST SNIPPET",
           }


def test_two_founder_reported_applications_never_accepted():
    result=evaluate(receipt(),[],now=NOW)
    assert result["publisher_id"]=="3136281"
    assert result["network_account_approved"]
    assert len(result["programmes"])==2
    assert result["candidate_count"]==0
    assert all(not row["advertiser_acceptance_verified"] for row in result["programmes"])
    assert all(not row["tracking_link_authorized"] for row in result["programmes"])
    assert not result["affiliate_publication_authorized"]
    assert not result["commission_paid_verified"]
    assert not result["email_verification_confirmed"]


def test_gmail_candidate_requires_human_review_not_approval():
    service=Service([email()])
    candidates=scan_awin_candidates(service,now=NOW)
    assert len(candidates)==1
    assert candidates[0]["advertiser_id"]=="73922"
    assert not candidates[0]["programme_accepted"]
    assert not candidates[0]["sender_authenticated_for_commercial_acceptance"]
    out=evaluate(receipt(),candidates,now=NOW)
    assert out["programmes"][1]["next_action"]=="REVIEW_AWIN_MESSAGE_AND_CHECK_DASHBOARD"
    assert not out["programmes"][1]["advertiser_acceptance_verified"]
    assert "NEVER PERSIST" not in str(candidates)+str(out)
    assert service.requests[1][1]["format"]=="metadata"


def test_spoofed_domain_rejected():
    fake=email(sender="scam@notawin.com")
    assert scan_awin_candidates(Service([fake]),now=NOW)==[]


def test_outbound_and_drafts_ignored():
    fake=email(labels=["SENT"])
    assert scan_awin_candidates(Service([fake]),now=NOW)==[]


def test_irrelevant_awin_invitation_ignored():
    assert scan_awin_candidates(Service([email(subject="Lush Lobster affiliate invite")]),now=NOW)==[]


def test_duplicate_gmail_identifiers_fail_closed():
    s=Service([email()])
    def bad_list(**kw):
        return Call({"messages":[{"id":"1234567890abcdef"},{"id":"1234567890abcdef"}]})
    s.list=bad_list
    with pytest.raises(AwinReviewHold):
        scan_awin_candidates(s,now=NOW)


def test_page_incomplete_blocks():
    s=Service([email()],extra={"nextPageToken":"more"})
    with pytest.raises(AwinReviewHold):
        scan_awin_candidates(s,now=NOW)


def test_invalid_programme_acceptance_claim_holds(tmp_path):
    data=receipt()
    data["advertiser_programmes"][0]["advertiser_acceptance_evidence"]=True
    p=write_src(tmp_path,data)
    with pytest.raises(AwinReviewHold):
        _private_receipt(p)


def test_private_source_and_symlink_hold(tmp_path):
    p=write_src(tmp_path)
    assert _private_receipt(p)["publisher_id"]=="3136281"
    p.chmod(0o644)
    with pytest.raises(AwinReviewHold):
        _private_receipt(p)
    p.unlink()
    target=tmp_path/"ordinary.json"
    target.write_text(json.dumps(receipt()))
    p.symlink_to(target)
    with pytest.raises(AwinReviewHold):
        _private_receipt(p)


def test_idempotent_snapshot_0600(tmp_path):
    write_src(tmp_path)
    class Provider:
        configured=True
        def _service(self):
            return Service([])
    a=run(root=tmp_path,provider=Provider(),write=True,now=NOW)
    assert a["snapshot_written"]
    path=tmp_path/OUTPUT
    assert stat.S_IMODE(path.stat().st_mode)==0o600
    old=path.read_bytes()
    b=run(root=tmp_path,provider=Provider(),write=True,now=NOW)
    assert b["snapshot_written"]
    assert path.read_bytes()==old
    assert b["database_writes"] is False and b["outbound_sent"] is False


def test_failure_does_not_overwrite_previous(tmp_path):
    p=write_src(tmp_path)
    class Provider:
        configured=True
        def _service(self):
            return Service([])
    assert run(root=tmp_path,provider=Provider(),write=True,now=NOW)["snapshot_written"]
    previous=(tmp_path/OUTPUT).read_bytes()
    p.write_text("{bad")
    result=run(root=tmp_path,provider=Provider(),write=True,now=NOW)
    assert result["status"].startswith("HELD_")
    assert (tmp_path/OUTPUT).read_bytes()==previous


def test_existing_unsafe_destination_blocks(tmp_path):
    p=tmp_path/OUTPUT
    p.parent.mkdir(parents=True)
    p.write_text("old")
    p.chmod(0o644)
    with pytest.raises(AwinReviewHold):
        _atomic_private_write(p,{"test":1})


def test_other_network_or_programme_never_inferred():
    with pytest.raises(AwinReviewHold):
        evaluate({"publisher_id":"something-else"},[],now=NOW)
