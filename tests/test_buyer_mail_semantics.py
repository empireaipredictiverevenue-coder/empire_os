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


def test_lead_smart_new_team_decision_reply_is_pending_not_approval():
    # Original latest buyer reply, 21 October 2026 10:41 UTC (no quoted history).
    body = ("Hi Phil,\\n\\nGot your message. This needs a decision from our "
            "team. We will get back to you.\\n\\nThanks, Lead Smart Support Agent")
    expected = ["BUYER_INTERNAL_DECISION_PENDING_REPORTED"]
    assert classify_visible_claims(body.replace("\\n", "\n")) == expected
    assert classify_visible_claims(body.replace("\\n", "\n"), outbound=True) == []
    for not_decision in (
        "We already tested your numbers and everything looks good. You can go live.",
        "Your payment terms are now approved and finalized.",
        "Please wait for the final landing screenshots approval.",
        "No need to make an internal decision from our team.",
    ):
        assert "BUYER_INTERNAL_DECISION_PENDING_REPORTED" not in classify_visible_claims(not_decision)
    quoted = "Thanks, got it.\nOn Wednesday, Buyer wrote:\nThis needs a decision from our team."
    assert "BUYER_INTERNAL_DECISION_PENDING_REPORTED" not in classify_visible_claims(quoted)


def test_pending_decision_event_flows_into_registry_without_launch_authority():
    from tests.test_connected_gmail_buyer_metadata import inputs
    old, index = inputs()
    inbound = index["threads"][0]["messages"][1]
    inbound["recognized_codes"] = ["BUYER_INTERNAL_DECISION_PENDING_REPORTED"]
    now = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)
    updated, _ = refreshed_summary(old, index, now=now)
    lead = next(x for x in updated["threads"] if x["entity_key"] == "lead-smart")
    assert lead["buyer_signal_events"][-1]["event_code"] == "BUYER_INTERNAL_DECISION_PENDING_REPORTED"
    report = reconcile(updated, {"candidate_count":0, "candidates":[]},
                       {"shortlisted_count":0, "targets":[]}, now=now,
                       do_not_pursue_domains=frozenset())
    row = next(x for x in report["relationships"] if x["entity_key"] == "lead-smart")
    assert any(e["event_code"] == "BUYER_INTERNAL_DECISION_PENDING_REPORTED"
               for e in row["automatically_recognized_buyer_events"])
    assert row["recognized_buyer_events_are_verified"] is False
    assert row["next_founder_action"] == "AWAIT_BUYER_INTERNAL_DECISION_NO_DUPLICATE_FOLLOWUP"
    assert row["founder_action_reason"] == "BUYER_REPORTED_INTERNAL_DECISION_PENDING"
    assert row["founder_review_required"] is True
    assert row["stage"] == "INBOUND_REVIEW_REQUIRED"
    assert row["outbound_authorized"] is False
    assert report["execution_authority"] == "NONE"

    # A newer, different inbound message supersedes the pending decision;
    # a founder suppression must also retain absolute priority.
    newer = deepcopy(updated)
    newer_lead = next(x for x in newer["threads"] if x["entity_key"] == "lead-smart")
    newer_lead["last_inbound_message_id"] = "abcdef0123456789"
    changed = reconcile(newer, {"candidate_count":0, "candidates":[]},
                        {"shortlisted_count":0, "targets":[]}, now=now,
                        do_not_pursue_domains=frozenset())
    latest = next(x for x in changed["relationships"] if x["entity_key"] == "lead-smart")
    assert latest["next_founder_action"] != "AWAIT_BUYER_INTERNAL_DECISION_NO_DUPLICATE_FOLLOWUP"
    suppressed = reconcile(updated, {"candidate_count":0, "candidates":[]},
                           {"shortlisted_count":0, "targets":[]}, now=now,
                           do_not_pursue_domains=frozenset({"leadsmartinc.com"}))
    blocked = next(x for x in suppressed["relationships"] if x["entity_key"] == "lead-smart")
    assert blocked["next_founder_action"] == "DO_NOT_PURSUE_NO_CONTACT"
    assert blocked["outbound_authorized"] is False


def test_revised_roofing_commercial_rules_are_recognized_only_from_direct_buyer_claims():
    buyer_reply = (
        "No. The range is from 60-150 seconds in total. "
        "If you send via the rtb the bid and duration are passed along to you.\n\n"
        "Yes, but the coverage tool updates 1 time a day, and buyers can pause "
        "and change throughout the day. The payout shown is also the top line "
        "payout and not the confirmed payout.\n\n"
        "ACH, Wire and PayPal are the only options."
    )
    code = "ROOFING_BUYER_REVISED_COMMERCIAL_TERMS_REPORTED"
    assert code in classify_visible_claims(buyer_reply)
    assert code not in classify_visible_claims(buyer_reply, outbound=True)
    assert code not in classify_visible_claims(
        "We have 60-150 seconds in total but the payout is confirmed and final. "
        "ACH, Wire and PayPal are the only options."
    )
    assert code not in classify_visible_claims(
        "The payout shown is the top line payout and not the confirmed payout."
    )
    assert code not in classify_visible_claims(
        "Thanks, understood.\nOn Wednesday, Lead Smart wrote:\n" + buyer_reply
    )


def test_latest_roofing_buyer_terms_correct_pending_decision_without_granting_authority():
    from tests.test_connected_gmail_buyer_metadata import inputs
    old, index = inputs()
    inbound = index["threads"][0]["messages"][1]
    inbound["recognized_codes"] = ["ROOFING_BUYER_REVISED_COMMERCIAL_TERMS_REPORTED"]
    now = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)
    updated, _ = refreshed_summary(old, index, now=now)
    report = reconcile(updated, {"candidate_count": 0, "candidates": []},
                       {"shortlisted_count": 0, "targets": []}, now=now,
                       do_not_pursue_domains=frozenset())
    row = next(x for x in report["relationships"] if x["entity_key"] == "lead-smart")
    assert row["next_founder_action"] == "REVIEW_LEAD_SMART_REVISED_TERMS_BEFORE_CALLS"
    assert row["founder_action_reason"] == "BUYER_REVISED_ROOFING_TERMS_REPORTED"
    assert row["founder_review_required"] is True
    assert row["recognized_buyer_events_are_verified"] is False
    assert row["commercial_buyer_approved"] is False
    assert row["outbound_authorized"] is False
    assert row["realised_revenue_proven"] is False
    assert report["execution_authority"] == "NONE"

    # A newer message, different buyer or suppression cannot inherit this status.
    different = deepcopy(updated)
    lead = next(x for x in different["threads"] if x["entity_key"] == "lead-smart")
    lead["last_inbound_message_id"] = "abcdef0123456789"
    revised = reconcile(different, {"candidate_count": 0, "candidates": []},
                        {"shortlisted_count": 0, "targets": []}, now=now,
                        do_not_pursue_domains=frozenset())
    lead_row = next(x for x in revised["relationships"] if x["entity_key"] == "lead-smart")
    assert lead_row["next_founder_action"] != "REVIEW_LEAD_SMART_REVISED_TERMS_BEFORE_CALLS"

    suppressed = reconcile(updated, {"candidate_count": 0, "candidates": []},
                           {"shortlisted_count": 0, "targets": []}, now=now,
                           do_not_pursue_domains=frozenset({"leadsmartinc.com"}))
    lead_row = next(x for x in suppressed["relationships"] if x["entity_key"] == "lead-smart")
    assert lead_row["next_founder_action"] == "DO_NOT_PURSUE_NO_CONTACT"
