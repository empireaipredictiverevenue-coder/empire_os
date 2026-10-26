"""V12: source custody, business-day cadence, buying-signal holds, replays."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import json
import stat

import pytest

from empire_os.heat_pump_relationship_lifecycle import (
    SCHEMA, SOURCE, OUTPUT, RelationshipHold, review,
    run_existing_buyer_team_review,
)
from empire_os.workspace_heat_pump_reply_tracking import ANCHORS, SCHEMA as SNAPSHOT_SCHEMA


NOW = datetime(2026, 10, 26, 19, 10, tzinfo=timezone.utc)


def snapshot(*, now=NOW):
    return {
        "schema_version": SNAPSHOT_SCHEMA,
        "status": "HEAT_PUMP_WORKSPACE_THREADS_REVIEW_ONLY",
        "mode": "OBSERVE", "scanned_at": now.isoformat(),
        "execution_authority": "none", "monitored_threads": 4,
        "verified_original_sends": 4,
        "outbound_sent": False, "database_writes": False,
        "automatic_reply_authorized": False,
        "commercial_buyer_acceptance_verified": False,
        "economic_memory_authorized": False,
        "payment_reconciled": False, "mailbox_full_coverage_verified": False,
        "inbound_header_candidate_count": 0,
        "threads": [{
            "company": name, "gmail_thread_id": tid,
            "original_sent_message_id": anchor,
            "original_sent_verified": True,
            "sent_at": "2026-10-24T14:00:00+00:00",
            "inbound_header_candidates": [],
            "buyer_terms_verified": False, "buyer_acceptance_verified": False,
            "payable_capacity_verified": False, "crm_promotion_authorized": False,
        } for name, tid, anchor in ANCHORS],
    }


def with_inbound(payload, *, msgid="abcdef0123456789", correspondence="EXACT_ORIGINAL_RECIPIENT"):
    p = deepcopy(payload)
    p["inbound_header_candidate_count"] += 1
    p["threads"][0]["inbound_header_candidates"].append({
        "gmail_message_id": msgid, "received_at": "2026-10-26T18:00:00+00:00",
        "sender_correspondence": correspondence,
        "rfc_parent_relation": "DIRECT_PARENT_MATCH",
        "status": "HEADER_CANDIDATE_HUMAN_VERIFICATION_REQUIRED",
    })
    return p


def test_wait_after_authenticated_sends_does_not_create_sales_ctas():
    out=review(snapshot(),None,now=NOW)
    assert out["schema_version"]==SCHEMA and out["sent_partner_relationships"]==4
    assert out["newly_due_founder_reviews"]==0
    assert all(r["review_action"]=="WAIT_FOR_RELATIONSHIP_REPLY_NO_REPEAT"
               and not r["sales_cta_authorized"] and not r["outbound_authorized"]
               and r["value_check_in_not_before_uk_date"]=="2026-10-30"
               for r in out["relationships"])
    assert out["buyer_acceptance_verified"] is False


def test_business_day_check_in_only_once_after_five_working_days():
    before=review(snapshot(),None,now=NOW)
    due=datetime(2026,10,30,13,tzinfo=timezone.utc)
    first=review(snapshot(now=due),before,now=due)
    assert first["newly_due_founder_reviews"]==4
    assert all(r["review_action"]=="CONSIDER_VALUE_FIRST_CHECK_IN_NO_SALES_CTA"
               for r in first["relationships"])
    repeated=review(snapshot(now=due),first,now=due)
    assert repeated["newly_due_founder_reviews"]==0
    assert all(not r["founder_review_newly_due"] for r in repeated["relationships"])


def test_one_new_reply_emits_review_only_once():
    source=with_inbound(snapshot())
    first=review(source,None,now=NOW)
    assert first["newly_due_founder_reviews"]==1
    assert first["relationships"][0]["review_action"]=="REVIEW_NEW_PARTNER_REPLY_FOR_NEEDS_AND_BUYING_SIGNAL"
    assert first["relationships"][0]["buying_signal_verified"] is False
    assert first["relationships"][0]["crm_promotion_authorized"] is False
    second=review(source,first,now=NOW)
    assert second["newly_due_founder_reviews"]==0
    assert second["relationships"][0]["review_action"]=="AWAIT_FOUNDER_REVIEW_NO_REPEAT"


def test_same_domain_contact_not_assumed_verified():
    first=review(with_inbound(snapshot(),correspondence="SAME_DOMAIN_DIFFERENT_ADDRESS"),None,now=NOW)
    assert first["newly_due_founder_reviews"]==1
    assert first["relationships"][0]["buying_signal_verified"] is False


def test_second_distinct_reply_is_not_lost():
    first=review(with_inbound(snapshot()),None,now=NOW)
    second_source=with_inbound(snapshot(),msgid="1122334455667788")
    second_source["threads"][0]["inbound_header_candidates"] += (
        with_inbound(snapshot())["threads"][0]["inbound_header_candidates"])
    second_source["inbound_header_candidate_count"]=2
    second=review(second_source,first,now=NOW)
    assert second["newly_due_founder_reviews"]==1
    assert second["relationships"][0]["new_header_candidates_for_review"]==["1122334455667788"]


@pytest.mark.parametrize("tamper", [
    lambda p: p.update(outbound_sent=True),
    lambda p: p.update(verified_original_sends=3),
    lambda p: p.update(commercial_buyer_acceptance_verified=True),
    lambda p: p.update(scanned_at="2026-10-25T00:00:00+00:00"),
    lambda p: p["threads"].pop(),
    lambda p: p["threads"][0].update(crm_promotion_authorized=True),
])
def test_unsafe_or_incomplete_snapshots_hold(tamper):
    source=snapshot()
    tamper(source)
    with pytest.raises(RelationshipHold):
        review(source,None,now=NOW)


def test_dropped_original_inbound_history_is_held():
    old=review(with_inbound(snapshot()),None,now=NOW)
    with pytest.raises(RelationshipHold,match="HISTORY_DROPPED"):
        review(snapshot(),old,now=NOW)


def test_bad_prior_state_does_not_reset_review_dedupe():
    with pytest.raises(RelationshipHold):
        review(snapshot(),{"schema_version":SCHEMA,"status":"RELATIONSHIP_REVIEW_EVIDENCE_ONLY"},now=NOW)


def test_run_persists_0600_snapshot_and_replay_safe(tmp_path):
    directory=tmp_path/SOURCE.parent
    directory.mkdir(parents=True)
    source=tmp_path/SOURCE
    source.write_text(json.dumps(snapshot()))
    source.chmod(0o600)
    first=run_existing_buyer_team_review(tmp_path,now=NOW)
    assert first["status"]=="RELATIONSHIP_REVIEW_EVIDENCE_ONLY"
    assert first["sent_partner_relationships"]==4 and first["newly_due_founder_reviews"]==0
    output=tmp_path/OUTPUT
    assert stat.S_IMODE(output.stat().st_mode)==0o600
    second=run_existing_buyer_team_review(tmp_path,now=NOW)
    assert second["newly_due_founder_reviews"]==0


def test_unsafe_source_symlink_fails_without_touching_output(tmp_path):
    directory=tmp_path/SOURCE.parent
    directory.mkdir(parents=True)
    external=tmp_path/"real_source.json"
    external.write_text(json.dumps(snapshot()))
    (tmp_path/SOURCE).symlink_to(external)
    result=run_existing_buyer_team_review(tmp_path,now=NOW)
    assert result["status"]=="HELD_RELATIONSHIP_EVIDENCE_UNAVAILABLE"
    assert not (tmp_path/OUTPUT).exists()


def test_no_fresh_source_cannot_overwrite_last_good_decisions(tmp_path):
    directory=tmp_path/SOURCE.parent
    directory.mkdir(parents=True)
    source=tmp_path/SOURCE
    source.write_text(json.dumps(snapshot()))
    source.chmod(0o600)
    assert run_existing_buyer_team_review(tmp_path,now=NOW)["sent_partner_relationships"]==4
    before=(tmp_path/OUTPUT).read_bytes()
    stale=datetime(2026,10,27,22,tzinfo=timezone.utc)
    assert run_existing_buyer_team_review(tmp_path,now=stale)["status"]=="HELD_RELATIONSHIP_EVIDENCE_UNAVAILABLE"
    assert (tmp_path/OUTPUT).read_bytes()==before
