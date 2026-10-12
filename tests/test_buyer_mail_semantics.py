"""Buyer Gmail recognition is read-only, bounded, source-bound and advisory."""
from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timezone
import json

import pytest

from empire_os.buyer_mail_semantics import (
    classify_visible_claims, recognize_message_payload,
)
from scripts.poll_buyer_gmail_readonly import collect, READ_SCOPE
from scripts.import_connected_gmail_buyer_metadata import refreshed_summary, THREADS
from empire_os.commercial_relationship_registry import reconcile, RelationshipEvidenceError

NOW = datetime(2026,10,12,9,20,tzinfo=timezone.utc)

def test_pending_signoff_is_not_approval_but_explicit_grant_is():
    pending = (
        "Seth will review the landing copy and reply with approval or changes. "
        "Until final landing approval please wait. When you send screenshots "
        "for visual sign-off, reply here."
    )
    approval = (
        "Hi, thanks for revised screenshots. If you still need our sign-off, "
        "you have it: you're approved and can go live now."
    )
    assert "LANDING_VISUAL_APPROVED_REPORTED" not in classify_visible_claims(pending)
    assert "LANDING_VISUAL_APPROVED_REPORTED" in classify_visible_claims(approval)

def test_recording_on_and_incomplete_call_do_not_imply_connected_buyer_leg():
    body = (
        "Recordings are enabled. This call did not have a recording as "
        "I hung up before connection.\n\nOn Sunday, Phil wrote:\n"
        "> Our buyer route is verified and calls connected."
    )
    assert set(classify_visible_claims(body)) == {
        "RECORDING_ENABLED_REPORTED",
        "TEST_ENDED_BEFORE_CONNECTION_REPORTED",
    }
    wrapped = "Recordings are enabled. This call did not have a recording as I hung up\nbefore connection."
    assert "TEST_ENDED_BEFORE_CONNECTION_REPORTED" in classify_visible_claims(wrapped)

def test_quoted_history_does_not_produce_approval():
    body = "Thanks, I'll check.\nOn 11 October, Buyer wrote:\nYou're approved and can go live now. Landing page approved."
    assert classify_visible_claims(body) == []

def test_raw_gmail_payload_never_returned_and_plain_mime_supported():
    body="Recordings are enabled."
    data=base64.urlsafe_b64encode(body.encode()).decode().rstrip("=")
    msg={"mimeType":"multipart/alternative","parts":[{"mimeType":"text/plain","body":{"data":data}}]}
    assert recognize_message_payload(msg) == ["RECORDING_ENABLED_REPORTED"]
    assert recognize_message_payload({"mimeType":"text/html","body":{"data":data}}) == ["RECORDING_ENABLED_REPORTED"]
    assert "Recordings" not in json.dumps(recognize_message_payload(msg))


class FakeThreads:
    def __init__(self, payload):self.payload=payload
    def get(self,**args):
        assert args['format']=='full'
        class Response:
            def __init__(self,p):self.p=p
            def execute(self):return self.p
        return Response(self.payload)
class FakeUsers:
    def __init__(self,p):self.p=p
    def threads(self):return FakeThreads(self.p)
class FakeService:
    def __init__(self,p):self.p=p
    def users(self):return FakeUsers(self.p)

def test_collector_persists_only_codes_for_trusted_buyer_sender():
    body="Recordings are enabled. This call did not have a recording as I hung up before connection."
    encoded=base64.urlsafe_b64encode(body.encode()).decode().rstrip("=")
    p={"messages":[{
        "id":"1a12d44d7e2f46a8","internalDate":"1791768000000",
        "labelIds":["INBOX"],"payload":{"mimeType":"text/plain",
        "body":{"data":encoded},"headers":[
            {"name":"From","value":"info@leadsmartinc.com"},
            {"name":"Subject","value":"Roofing"}
        ]}
    }]}
    domains={"lead-smart":["leadsmartinc.com"]}
    report=collect(FakeService(p),now=NOW,known_domains=domains)
    lead=next(x for x in report["threads"] if x['thread_id']=="1a0d9ce883c87d4a")
    message=lead["messages"][0]
    assert sorted(message["recognized_codes"]) == [
        "RECORDING_ENABLED_REPORTED","TEST_ENDED_BEFORE_CONNECTION_REPORTED"
    ]
    serialized=json.dumps(report)
    assert "hung up before connection" not in serialized
    assert encoded not in serialized
    # Unrelated sender cannot manufacture a statement merely by appearing in
    # a familiar Gmail thread.
    spoof=deepcopy(p)
    spoof["messages"][0]["payload"]["headers"][0]["value"]="unknown@elsewhere.com"
    other=collect(FakeService(spoof),now=NOW,known_domains=domains)
    msg=other["threads"][0]["messages"][0]
    assert "recognized_codes" not in msg
    assert READ_SCOPE.endswith("gmail.readonly")


def test_recognized_buyer_claims_pass_from_gmail_to_founder_registry_without_authority():
    from tests.test_connected_gmail_buyer_metadata import inputs
    now=datetime(2026,10,10,12,0,tzinfo=timezone.utc)
    old,index=inputs()
    inbound=index["threads"][0]["messages"][1]
    inbound["recognized_codes"]=[
        "RECORDING_ENABLED_REPORTED","TEST_ENDED_BEFORE_CONNECTION_REPORTED"
    ]
    updated,meta=refreshed_summary(old,index,now=now)
    row=next(x for x in updated["threads"] if x["entity_key"]=="lead-smart")
    assert len(row["buyer_signal_events"])==2
    assert all(x["evidence_grade"]=="EMAIL_REPORTED_UNVERIFIED"
               for x in row["buyer_signal_events"])
    report=reconcile(updated,{"candidate_count":0,"candidates":[]},
                     {"shortlisted_count":0,"targets":[]},now=now,
                     do_not_pursue_domains=frozenset())
    r=next(x for x in report["relationships"] if x["entity_key"]=="lead-smart")
    assert len(r["automatically_recognized_buyer_events"])==2
    assert r["recognized_buyer_events_are_verified"] is False
    assert not r["outbound_authorized"]
    assert report["outbound_authorized"] is False
    assert report["execution_authority"]=="NONE"
    assert "body" not in json.dumps(r)


@pytest.mark.parametrize("code",[
    "ACTIVATE_TRAFFIC","ROUTE_VERIFIED","LANDING_VISUAL_APPROVED_REPORTED",
])
def test_forged_or_wrong_direction_event_cannot_enter_buyer_registry(code):
    from tests.test_connected_gmail_buyer_metadata import inputs
    old,index=inputs()
    # The outbound original cannot carry an inbound-reported event;
    # unknown magic commands cannot grant authority either.
    index["threads"][0]["messages"][0]["recognized_codes"]=[code]
    with pytest.raises(RelationshipEvidenceError,match="RECOGNITION"):
        refreshed_summary(old,index,now=datetime(2026,10,10,12,0,tzinfo=timezone.utc))


def test_new_engaged_buyer_full_requirement_request_needs_no_hardcoded_ids():
    from empire_os.commercial_relationship_registry import reviewed_request_duplicate_guard
    message=(
        "Hi Sarah, could you send your live campaign buy-box and accepted jobs, "
        "payout and settlement terms, routing and original caller ID, "
        "recording and consent requirements, and partner agreement/onboarding? "
        "An existing pack is fine."
    )
    codes=classify_visible_claims(message,outbound=True)
    assert "COMPLETE_BUYER_REQUIREMENTS_SENT" in codes
    assert "COMPLETE_BUYER_REQUIREMENTS_SENT" not in classify_visible_claims(message)
    guard=reviewed_request_duplicate_guard("future-roofing-buyer",{
        "gmail_thread_ids":["abcdef1234567890"],
        "last_outbound_message_id":"0123456789abcdef",
        "gmail_snapshot_fresh":True,
        "buyer_signal_events":[{
            "message_id":"0123456789abcdef",
            "event_code":"COMPLETE_BUYER_REQUIREMENTS_SENT",
            "observed_at":"2026-10-12T09:12:00Z",
            "evidence_grade":"EMAIL_REPORTED_UNVERIFIED",
            "direction":"outbound",
        }],
    })
    assert guard["status"]=="PRIOR_FULL_REQUEST_SENT"
    assert guard["request_provenance"]=="gmail:0123456789abcdef"
    assert guard["repeat_full_request_allowed"] is False
    assert guard["outbound_authorized"] is False


def test_html_only_publisher_response_reports_paid_placements_without_quoted_history():
    body=(
        '<html><body><div>Hi Phil,</div><div>We only do sponsored posts, guest posts, '
        'and link placements in existing content as part of collaborations.</div>'
        '<blockquote>Our landing page is approved and route live.</blockquote>'
        '<div class="gmail_quote">You have our sign-off; you\'re approved and can go live.</div>'
        '<script>We approved your calls.</script></body></html>'
    )
    encoded=base64.urlsafe_b64encode(body.encode()).decode().rstrip('=')
    events=recognize_message_payload({"mimeType":"text/html","body":{"data":encoded}})
    assert events==["PUBLISHER_SPONSORED_PLACEMENTS_ONLY_REPORTED"]
