"""Guarded founder acquisition runner: never promote guesses to an outbound decision."""
from datetime import datetime, timezone
from pathlib import Path
import csv
import json
import shutil

import pytest

from empire_os.founder_acquisition_autopilot import (
    EXPECTED_SENT, PLENA, SOURCE, EvidenceHeld, load_ledger, review_threads,
)
from scripts.run_founder_acquisition_review import run

CLOCK = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)


def fixture_ledger(tmp_path):
    path = tmp_path / SOURCE
    path.parent.mkdir(parents=True)
    shutil.copy(Path(__file__).resolve().parent.parent / SOURCE, path)
    return load_ledger(tmp_path)


def sent_message(tid, address):
    return {
        "id": tid, "threadId": tid, "labelIds": ["SENT"],
        "internalDate": "1792750000000",
        "payload": {"headers": [
            {"name": "From", "value": "Phil <phil@empire-ai.co.uk>"},
            {"name": "To", "value": address},
            {"name": "Message-ID", "value": "<legitimate@empire-ai.co.uk>"},
        ]},
    }


def inbound_message(tid, address, *, ident="bb99999999999999", when="1792750300000"):
    return {
        "id": ident, "threadId": tid, "labelIds": ["INBOX"],
        "internalDate": when,
        "payload": {"headers": [
            {"name": "From", "value": address},
            {"name": "To", "value": "phil@empire-ai.co.uk"},
            {"name": "Message-ID", "value": "<followup@prospect.example>"},
            {"name": "In-Reply-To", "value": "<legitimate@empire-ai.co.uk>"},
        ]},
    }


def fixture_results(ledger):
    return {tid: {"id": tid, "messages": [sent_message(tid, addr)]}
            for _, addr, tid in ledger["anchors"]}


class FakeService:
    def __init__(self, results):
        self.results = results
    def users(self):
        return self
    def threads(self):
        return self
    def messages(self):
        return self
    def list(self, **kwargs):
        self.action = "list"
        return self
    def get(self, **kwargs):
        self.action = "get"
        self.selected = kwargs["id"]
        return self
    def execute(self):
        if self.action == "list":
            return {"messages": []}
        return self.results[self.selected]


class FakeProvider:
    configured = True
    def __init__(self, results):
        self.results = results
    def _service(self):
        return FakeService(self.results)


def test_ledger_exact_sends_and_pending(tmp_path):
    ledger = fixture_ledger(tmp_path)
    assert len(ledger["anchors"]) == 9
    assert len(ledger["pending"]) == 8
    assert len({x[2] for x in ledger["anchors"]}) == 9
    assert ledger["anchors"][0] == PLENA


def test_refuse_tampered_sent_receipt(tmp_path):
    fixture_ledger(tmp_path)
    p = tmp_path / SOURCE
    with p.open() as f:
        fields = csv.DictReader(f).fieldnames
    with p.open() as f:
        rows = list(csv.DictReader(f))
    next(r for r in rows if r["company"] == "Andco")["gmail_sent_message_id"] = "0000000000000000"
    with p.open("w") as f:
        w = csv.DictWriter(f, fieldnames=fields);w.writeheader();w.writerows(rows)
    with pytest.raises(EvidenceHeld, match="SENT_PROVIDER_RECEIPT_MISMATCH"):
        load_ledger(tmp_path)


def test_exact_nine_provider_anchors_are_review_only(tmp_path):
    ledger = fixture_ledger(tmp_path)
    reviewed = review_threads(ledger, fixture_results(ledger), now=CLOCK)
    assert reviewed["status"] == "SOURCE_ANCHORS_VERIFIED_REVIEW_ONLY"
    assert reviewed["sent_anchors_verified"] == 9
    assert reviewed["inbound_header_candidate_count"] == 0
    assert len(reviewed["next_unsent_review"]) == 8
    assert reviewed["outbound_sent"] is False
    assert reviewed["automatic_reply_authorized"] is False
    assert reviewed["canonical_suppression_verified"] is False
    assert reviewed["canonical_email_clearance_evidence_missing_count"] == 9
    assert reviewed["canonical_email_clearance_status"] == "NOT_VERIFIED"
    assert reviewed["governed_outbound_release_eligible"] is False
    assert reviewed["paid_pilot_authorized"] is False


def test_one_new_inbound_is_not_buying_interest(tmp_path):
    ledger = fixture_ledger(tmp_path)
    r = fixture_results(ledger)
    _, addr, tid = ledger["anchors"][1]
    r[tid]["messages"].append(inbound_message(tid, addr))
    v = review_threads(ledger, r, now=CLOCK)
    assert v["new_inbound_header_candidates"] == 1
    assert v["inbound_header_candidate_count"] == 1
    assert v["threads"][1]["buyer_intent_verified"] is False
    assert v["threads"][1]["reply_body_verified"] is False
    assert all("@" not in json.dumps(x) for x in v["threads"])


def test_repeat_run_does_not_duplicate_reply(tmp_path):
    ledger = fixture_ledger(tmp_path)
    r = fixture_results(ledger)
    _, addr, tid = ledger["anchors"][1]
    r[tid]["messages"].append(inbound_message(tid, addr))
    first = review_threads(ledger, r, now=CLOCK)
    again = review_threads(ledger, r, now=CLOCK, previous=first)
    assert again["new_inbound_header_candidates"] == 0
    assert again["inbound_header_candidate_count"] == 1


def test_drop_or_mismatch_existing_thread_fails_closed(tmp_path):
    ledger = fixture_ledger(tmp_path)
    r = fixture_results(ledger)
    r.pop(PLENA[2])
    with pytest.raises(EvidenceHeld, match="INCOMPLETE_OR_EXTRA_THREAD_COVERAGE"):
        review_threads(ledger, r, now=CLOCK)
    r = fixture_results(ledger)
    r[PLENA[2]]["messages"][0]["payload"]["headers"][0]["value"] = "Malicious <other@example.com>"
    with pytest.raises(EvidenceHeld, match="SENT_ANCHOR_NOT_PROVEN"):
        review_threads(ledger, r, now=CLOCK)


def test_unrelated_sender_not_a_reply(tmp_path):
    ledger = fixture_ledger(tmp_path)
    r = fixture_results(ledger)
    _, _, tid = ledger["anchors"][1]
    r[tid]["messages"].append(inbound_message(tid, "third-party@other.example"))
    v = review_threads(ledger, r, now=CLOCK)
    assert v["inbound_header_candidate_count"] == 0


def test_existing_snapshot_must_not_lose_inbound(tmp_path):
    ledger = fixture_ledger(tmp_path)
    r = fixture_results(ledger)
    _, addr, tid = ledger["anchors"][1]
    r[tid]["messages"].append(inbound_message(tid, addr))
    old = review_threads(ledger, r, now=CLOCK)
    r[tid]["messages"].pop()
    with pytest.raises(EvidenceHeld, match="PREVIOUS_REPLIES_DISAPPEARED"):
        review_threads(ledger, r, now=CLOCK, previous=old)


def test_runner_writes_private_snapshot_and_no_actions(tmp_path):
    ledger = fixture_ledger(tmp_path)
    provider = FakeProvider(fixture_results(ledger))
    result = run(tmp_path, provider=provider, now=CLOCK, write=True,
                 source_fetch=lambda url: (_ for _ in ()).throw(RuntimeError("offline test")))
    assert result["status"] == "SOURCE_ANCHORS_VERIFIED_REVIEW_ONLY"
    assert result["monitored_threads"] == 9
    assert result["snapshot_written"] is True
    assert result["outbound_sent"] is False
    assert result["database_writes"] is False
    out = tmp_path / "runtime/founder_acquisition/founder_reply_review_latest.json"
    assert out.exists() and out.stat().st_mode & 0o077 == 0
    assert run(tmp_path, provider=provider, now=CLOCK, write=True,
               source_fetch=lambda url: (_ for _ in ()).throw(RuntimeError("offline test")))["new_inbound_header_candidates"] == 0


def test_runner_blocks_unsafe_previous_snapshot(tmp_path):
    ledger = fixture_ledger(tmp_path)
    provider = FakeProvider(fixture_results(ledger))
    out = tmp_path / "runtime/founder_acquisition/founder_reply_review_latest.json"
    out.parent.mkdir(parents=True)
    out.write_text("{}")
    assert run(tmp_path, provider=provider, now=CLOCK, write=True)["status"] == "HELD_NOT_AUTHENTICATED"


def test_safe_new_candidate_can_be_appended_without_send_authority(tmp_path):
    fixture_ledger(tmp_path)
    path = tmp_path / SOURCE
    with path.open() as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        rows = list(reader)
    extra = dict(rows[-1])
    extra.update(company="FutureSourceAI", published_contact="founders@futuresource.ai",
                 yc_original_source="https://www.ycombinator.com/companies/futuresource",
                 email_first_draft_status="NOT_DRAFTED", outbound_approval="NONE",
                 gmail_sent_message_id="", gmail_sent_thread_id="")
    rows.append(extra)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    v = load_ledger(tmp_path)
    assert len(v["pending"]) == 9
    extra["outbound_approval"] = "FOUNDER_APPROVED"
    rows[-1] = extra
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(EvidenceHeld, match="UNREVIEWED_CANDIDATE_CANNOT_INHERIT_APPROVAL"):
        load_ledger(tmp_path)


def test_original_seven_thread_snapshot_migrates_without_losing_replies(tmp_path):
    ledger = fixture_ledger(tmp_path)
    payloads = fixture_results(ledger)
    older = dict(payloads)
    for name, addr, tid in ledger['anchors']:
        if name in ('LunaBill', 'ProhostAI'):
            older.pop(tid)
    historic = review_threads(
        {'anchors': [a for a in ledger['anchors']
                     if a[0] not in ('LunaBill','ProhostAI')],
         'pending': []}, older, now=CLOCK)
    # One earlier seven-cohort candidate stays preserved across expansion.
    old_company, old_email, old_tid = ledger['anchors'][1]
    older[old_tid]['messages'].append(inbound_message(old_tid,old_email))
    historic = review_threads(
        {'anchors':[a for a in ledger['anchors']
                    if a[0] not in ('LunaBill','ProhostAI')],
         'pending': []}, older, now=CLOCK)
    payloads[old_tid] = older[old_tid]
    migrated = review_threads(ledger,payloads,now=CLOCK,previous=historic)
    assert migrated['monitored_threads']==9
    assert migrated['sent_anchors_verified']==9
    assert migrated['inbound_header_candidate_count']==1
    assert migrated['new_inbound_header_candidates']==0
    assert next(x for x in migrated['threads'] if x['company']==old_company)['inbound_header_candidates']==['bb99999999999999']
    assert migrated['outbound_sent'] is False
    assert all(row['buyer_intent_verified'] is False for row in migrated['threads'])


def test_reject_seven_history_with_replaced_prior_sent_anchor(tmp_path):
    ledger=fixture_ledger(tmp_path)
    all_msgs=fixture_results(ledger)
    prior=review_threads(ledger,all_msgs,now=CLOCK)
    prior['threads']=prior['threads'][:6]+[prior['threads'][7]]
    # This lacks one of the original seven known anchors and includes a new
    # send; it is not the authorised 7-to-9 migration state.
    with pytest.raises(EvidenceHeld,match='PREVIOUS_THREAD_COVERAGE_CHANGED'):
        review_threads(ledger,all_msgs,now=CLOCK,previous=prior)
