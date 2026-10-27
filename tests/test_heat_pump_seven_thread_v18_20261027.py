"""V18: seven real Workspace sent anchors, four-to-seven receipt migration."""
from copy import deepcopy
from datetime import datetime, timezone
import pytest

from empire_os.workspace_heat_pump_reply_tracking import (
    ANCHORS, EXPECTED, LEGACY_ANCHORS, SCHEMA,
    newly_observed_heat_pump_candidates, review_heat_pump_threads
)
from empire_os.heat_pump_relationship_lifecycle import (
    review as lifecycle_review, RelationshipHold, SCHEMA as LIFECYCLE_SCHEMA,
)
from empire_os.workspace_solar_reply_tracking import EvidenceHeld

NOW = datetime(2026, 10, 27, 9, 51, tzinfo=timezone.utc)
SENT = datetime(2026, 10, 26, 23, 9, tzinfo=timezone.utc)
RECEIPT = {
    "status": "HEADER_CANDIDATE_HUMAN_VERIFICATION_REQUIRED",
    "received_at": "2026-10-27T07:30:00+00:00",
    "sender_correspondence": "EXACT_ORIGINAL_RECIPIENT",
    "rfc_parent_relation": "DIRECT_PARENT_MATCH",
    "gmail_message_id": "aa11bb22cc33dd44",
}


def make_snapshot(anchors=ANCHORS, *, inbound_company=None):
    rows = []
    for company, tid, anchor in anchors:
        rows.append({
            "company": company, "gmail_thread_id": tid,
            "original_sent_message_id": anchor, "original_sent_verified": True,
            "sent_at": SENT.isoformat(),
            "inbound_header_candidates": (
                [dict(RECEIPT)] if company == inbound_company else []),
            "buyer_terms_verified": False, "buyer_acceptance_verified": False,
            "payable_capacity_verified": False, "crm_promotion_authorized": False,
        })
    return {
        "schema_version": SCHEMA,
        "status": "HEAT_PUMP_WORKSPACE_THREADS_REVIEW_ONLY",
        "scanned_at": NOW.isoformat(), "monitored_threads": len(rows),
        "verified_original_sends": len(rows),
        "inbound_header_candidate_count": int(inbound_company is not None),
        "threads": rows, "mode": "OBSERVE",
        "execution_authority": "none",
        "automatic_reply_authorized": False,
        "commercial_buyer_acceptance_verified": False,
        "outbound_sent": False, "database_writes": False,
        "mailbox_full_coverage_verified": False,
        "payment_reconciled": False,
        "economic_memory_authorized": False,
    }


def old_relationship_state():
    record = {
        "schema_version": LIFECYCLE_SCHEMA,
        "status": "RELATIONSHIP_REVIEW_EVIDENCE_ONLY",
        "outbound_authorized": False,
        "crm_promotion_authorized": False,
        "buyer_acceptance_verified": False,
        "seen_inbound_message_ids": {tid: [] for _,tid,_ in LEGACY_ANCHORS},
        "value_review_already_surfaced": [],
    }
    return record


def test_all_real_seven_exact_gmail_ids():
    assert len(ANCHORS) == 7 and len(EXPECTED) == 7
    assert ANCHORS[:4] == LEGACY_ANCHORS
    assert ANCHORS[4:] == (
        ("Good Energy","1a17a526f6945efa","1a17a797e5a9f0e9"),
        ("Alto Energy","1a17a5272d0e2a39","1a17a79980d72432"),
        ("Appian Heat Pumps","1a17a527931e2d31","1a17a79a9700c50f"),
    )


def test_first_seven_thread_scan_migrates_original_four_without_fake_replies():
    prior = make_snapshot(LEGACY_ANCHORS)
    current = make_snapshot()
    assert newly_observed_heat_pump_candidates(current,prior) == 0
    assert newly_observed_heat_pump_candidates(current,current) == 0
    outcome = lifecycle_review(current,old_relationship_state(),now=NOW)
    assert outcome["sent_partner_relationships"] == 7
    assert outcome["inbound_header_candidates"] == 0
    assert outcome["newly_due_founder_reviews"] == 0
    assert len(outcome["seen_inbound_message_ids"]) == 7
    assert len(outcome["relationships"]) == 7
    assert outcome["outbound_authorized"] is False
    assert outcome["buyer_acceptance_verified"] is False
    assert outcome["payment_authorized"] is False
    assert outcome["automatic_email_authorized"] is False


def test_preserve_original_four_reply_history_and_one_new_header():
    prior = make_snapshot(LEGACY_ANCHORS,inbound_company="C12 Energy")
    current = make_snapshot(inbound_company="C12 Energy")
    assert newly_observed_heat_pump_candidates(current,prior) == 0
    relationship = old_relationship_state()
    relationship["seen_inbound_message_ids"][LEGACY_ANCHORS[0][1]] = [
        RECEIPT["gmail_message_id"]]
    relationship["value_review_already_surfaced"] = [LEGACY_ANCHORS[1][1]]
    review = lifecycle_review(current,relationship,now=NOW)
    assert review["newly_due_founder_reviews"] == 0
    assert review["value_review_already_surfaced"] == [LEGACY_ANCHORS[1][1]]
    assert review["seen_inbound_message_ids"][LEGACY_ANCHORS[0][1]] == [
        RECEIPT["gmail_message_id"]]


def test_new_header_candidate_counted_once_not_as_accepted_buyer():
    prior = make_snapshot(LEGACY_ANCHORS)
    current = make_snapshot(inbound_company="Alto Energy")
    assert newly_observed_heat_pump_candidates(current,prior) == 1
    migrated = lifecycle_review(current, old_relationship_state(), now=NOW)
    assert migrated["newly_due_founder_reviews"] == 1
    assert migrated["inbound_header_candidates"] == 1
    new = [x for x in migrated["relationships"] if x["company"]=="Alto Energy"][0]
    assert new["review_action"]=="REVIEW_NEW_PARTNER_REPLY_FOR_NEEDS_AND_BUYING_SIGNAL"
    assert new["buyer_terms_verified"] is False
    assert new["outbound_authorized"] is False
    assert lifecycle_review(current,migrated,now=NOW)["newly_due_founder_reviews"] == 0
    assert newly_observed_heat_pump_candidates(current,current) == 0


def test_migration_rejects_missing_original_or_rogue_entries():
    old=make_snapshot(LEGACY_ANCHORS)
    current=make_snapshot()
    current["threads"][0]["original_sent_message_id"] = "abc1234567891234"
    with pytest.raises(EvidenceHeld):
        newly_observed_heat_pump_candidates(current,old)
    current=make_snapshot()
    old["threads"][0]["original_sent_message_id"] = "abc1234567891234"
    with pytest.raises(EvidenceHeld):
        newly_observed_heat_pump_candidates(current,old)
    state=old_relationship_state()
    state["seen_inbound_message_ids"]["rogue-thread"]=[]
    with pytest.raises(RelationshipHold):
        lifecycle_review(make_snapshot(),state,now=NOW)


def test_no_silent_drop_existing_header_or_fabricated_approval():
    prior=make_snapshot(LEGACY_ANCHORS,inbound_company="C12 Energy")
    current=make_snapshot()
    with pytest.raises(EvidenceHeld):
        newly_observed_heat_pump_candidates(current,prior)
    rel=old_relationship_state()
    rel["seen_inbound_message_ids"][LEGACY_ANCHORS[0][1]]=[RECEIPT["gmail_message_id"]]
    with pytest.raises(RelationshipHold):
        lifecycle_review(current,rel,now=NOW)
    current["commercial_buyer_acceptance_verified"]=True
    with pytest.raises(EvidenceHeld):
        newly_observed_heat_pump_candidates(current,None)


def test_strict_current_seven_not_partial_four():
    with pytest.raises(EvidenceHeld):
        newly_observed_heat_pump_candidates(make_snapshot(LEGACY_ANCHORS), None)
    with pytest.raises(RelationshipHold):
        lifecycle_review(make_snapshot(LEGACY_ANCHORS), None, now=NOW)


def test_provider_response_seven_thread_shape_no_contact_body_kept():
    ms=str(int(SENT.timestamp()*1000))
    threads={}
    for company,tid,anchor in ANCHORS:
        headers=[
            {"name":"From","value":"Phil <phil@mail.empire-ai.co.uk>"},
            {"name":"To","value":"partners@example.com"},
            {"name":"Message-ID","value":"<anchor@example.com>"},
        ]
        threads[tid]={"id":tid,"messages":[{
            "id":anchor,"threadId":tid,"internalDate":ms,
            "labelIds":["SENT"],"payload":{"headers":headers},
            "snippet":"should-not-be-retained",
        }]}
    result=review_heat_pump_threads(threads,now=NOW)
    assert result["verified_original_sends"]==7
    assert result["monitored_threads"]==7
    assert result["inbound_header_candidate_count"]==0
    assert "should-not-be-retained" not in str(result)
    assert result["outbound_sent"] is False
