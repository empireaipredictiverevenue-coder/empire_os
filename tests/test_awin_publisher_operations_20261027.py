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
def test_skillforge_discovers_exact_affiliate_task_but_never_self_approves():
    from pathlib import Path
    from empire_os.skill_exchange import discover_task_skills, recommend_work_item_skills
    from empire_os.skill_trust import load_work_item_skill_context
    root=Path(__file__).resolve().parents[1]
    skillroot=root/"empire_os/skills_library/skills"
    found=discover_task_skills("affiliate_publisher_operations",root=skillroot)
    assert found["status"]=="local_candidates"
    assert [x["name"] for x in found["skills"]]==["empire-affiliate-publisher-operations"]
    target={"id":"awin-3136281-observe","department_keys":["sales"],
            "target_component":"awin_affiliate_publisher_operations"}
    choices=recommend_work_item_skills(target,root=skillroot)
    assert choices["skill_recommendations"][0]["skills"][0]["name"]=="empire-affiliate-publisher-operations"
    gated=load_work_item_skill_context(target,root=skillroot,registry={
        "schema_version":"empire.skill_trust.v1","approved_skills":{}
    })
    assert gated["skills"]==[]
    assert gated["rejected"][0]["reason"]=="skill_not_approved"
    assert gated["execution_authority"]=="none"



def test_real_new_candidate_only_once_without_resending(tmp_path):
    write_src(tmp_path)

    class Provider:
        configured = True
        def __init__(self):
            self.messages = [email()]
        def _service(self):
            return Service(self.messages)

    provider = Provider()
    first = run(root=tmp_path, provider=provider, write=True, now=NOW)
    assert first["status"]=="AWIN_NETWORK_APPROVED_PROGRAMME_APPLICATIONS_PENDING_REVIEW"
    assert first["new_potential_inbound_headers"] == 1
    assert first["potential_inbound_headers"] == 1
    path = tmp_path / OUTPUT
    one = json.loads(path.read_text())
    assert one["programmes"][1]["new_inbound_header_candidates"] == 1
    second = run(root=tmp_path, provider=provider, write=True, now=NOW)
    assert second["new_potential_inbound_headers"] == 0
    assert second["potential_inbound_headers"] == 1
    two = json.loads(path.read_text())
    assert two["programmes"][1]["new_inbound_header_candidates"] == 0
    assert one["seen_programme_message_refs"] == two["seen_programme_message_refs"]
    assert all(not x["advertiser_acceptance_verified"] for x in two["programmes"])


def test_candidate_history_survives_shorter_window(tmp_path):
    write_src(tmp_path)

    class Provider:
        configured = True
        def __init__(self):
            self.messages = [email()]
        def _service(self):
            return Service(self.messages)

    provider = Provider()
    first = run(root=tmp_path,provider=provider,write=True,now=NOW)
    assert first["new_potential_inbound_headers"] == 1
    provider.messages = []
    no_longer_visible = run(root=tmp_path,provider=provider,write=True,now=NOW)
    assert no_longer_visible["new_potential_inbound_headers"] == 0
    provider.messages = [email()]
    return_to_view = run(root=tmp_path,provider=provider,write=True,now=NOW)
    assert return_to_view["new_potential_inbound_headers"] == 0
    assert return_to_view["potential_inbound_headers"] == 1


def test_old_v1_private_snapshot_migrates_without_duplicate(tmp_path):
    write_src(tmp_path)
    existing = evaluate(receipt(),scan_awin_candidates(Service([email()]),now=NOW),now=NOW)
    existing.pop("seen_programme_message_refs",None)
    existing.pop("new_candidate_count",None)
    for item in existing["programmes"]:
        item.pop("inbound_header_candidate_count",None)
    _atomic_private_write(tmp_path/OUTPUT,existing)
    class Provider:
        configured = True
        def _service(self):
            return Service([email()])
    r=run(root=tmp_path,provider=Provider(),write=True,now=NOW)
    assert r["status"]=="AWIN_NETWORK_APPROVED_PROGRAMME_APPLICATIONS_PENDING_REVIEW"
    assert r["new_potential_inbound_headers"]==0


def test_tampered_old_snapshot_preserved_and_held(tmp_path):
    write_src(tmp_path)
    path=tmp_path/OUTPUT
    initial=evaluate(receipt(),[],now=NOW)
    initial["execution_authority"]="LIVE"
    _atomic_private_write(path,initial)
    data=path.read_bytes()
    class Provider:
        configured = True
        def _service(self):
            return Service([email()])
    r=run(root=tmp_path,provider=Provider(),write=True,now=NOW)
    assert r["status"].startswith("HELD_")
    assert not r["snapshot_written"]
    assert path.read_bytes()==data


def test_gmail_search_bounded_to_authorised_provider_domains():
    service=Service([email()])
    scan_awin_candidates(service,now=NOW)
    q=service.requests[0][1]["q"]
    assert "from:awin.com" in q
    assert "from:ovoenergy.com" in q
    assert "from:glowgreenltd.com" in q
    assert " -in:trash" in q
