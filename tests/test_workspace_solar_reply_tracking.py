"""Provider-metadata-only first-party Workspace solar outreach tracking tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from copy import deepcopy

import pytest

from empire_os.workspace_solar_reply_tracking import (
    ANCHORS, ACCOUNT, SCHEMA, EvidenceHeld, collect_workspace_solar_threads,
    review_workspace_solar_threads,
)
from scripts.poll_workspace_solar_outreach_readonly import run

NOW = datetime(2026, 10, 18, 14, 0, tzinfo=timezone.utc)
SENT_AT = datetime(2026, 10, 18, 13, 32, tzinfo=timezone.utc)
REPLIED_AT = datetime(2026, 10, 18, 13, 50, tzinfo=timezone.utc)


def msg(mid, tid, *, sender, recipient, when=SENT_AT, labels=None, subject="Confidential customer text not retained"):
    return {
        "id": mid, "threadId": tid, "internalDate": str(int(when.timestamp() * 1000)),
        "labelIds": list(labels or ["SENT"]),
        "payload": {"headers": [
            {"name": "From", "value": sender},
            {"name": "To", "value": recipient},
            {"name": "Subject", "value": subject},
        ]},
        "snippet": "Private body is deliberately ignored",
    }


@pytest.fixture
def six_threads():
    return {
        tid: {"id": tid, "messages": [
            msg(sent, tid, sender="Phil - Founder - Empire AI <" + ACCOUNT + ">",
                recipient=recipient)
        ]}
        for _, _, recipient, tid, sent in ANCHORS
    }


def test_exact_six_existing_gmail_sent_anchors_prove_only_outbound(six_threads):
    result = review_workspace_solar_threads(six_threads, now=NOW)
    assert result["schema_version"] == SCHEMA
    assert result["monitored_threads"] == result["verified_sent_anchors"] == 6
    assert result["inbound_header_candidate_count"] == 0
    assert result["founder_crm_ingest_verified"] is False
    assert result["gmail_message_bodies_retained"] is False
    assert result["gmail_subjects_retained"] is False
    assert result["outbound_sent"] is False
    assert result["recognized_revenue"] is False
    assert all(item["inbound_header_candidates"] == [] for item in result["threads"])
    assert "Confidential customer text" not in str(result)


def test_incoming_message_in_exact_thread_is_review_candidate_not_buyer_reply(six_threads):
    company, domain, recipient, tid, sent = ANCHORS[0]
    six_threads[tid]["messages"].append(
        msg("1a14f9e381121111", tid, sender=f"Team <inbox@{domain}>",
            recipient=ACCOUNT, when=REPLIED_AT, labels=["INBOX", "UNREAD"])
    )
    result = review_workspace_solar_threads(six_threads, now=NOW)
    assert result["inbound_header_candidate_count"] == 1
    inbound = result["threads"][0]["inbound_header_candidates"][0]
    assert inbound["gmail_message_id"] == "1a14f9e381121111"
    assert inbound["status"] == "INBOUND_PROVIDER_HEADER_CANDIDATE_NEEDS_HUMAN_REVIEW"
    assert result["threads"][0]["buyer_intent_verified"] is False
    assert result["threads"][0]["inbound_corroborated_by_body"] is False
    assert "inbox@" not in str(result)


@pytest.mark.parametrize("key", ["SENT", "DRAFT", "SPAM", "TRASH"])
def test_inbound_mislabelled_messages_do_not_count(six_threads, key):
    _, domain, _, tid, _ = ANCHORS[0]
    six_threads[tid]["messages"].append(
        msg("1a14f9e381121111", tid, sender=f"someone@{domain}",
            recipient=ACCOUNT, when=REPLIED_AT, labels=[key])
    )
    assert review_workspace_solar_threads(six_threads, now=NOW)["inbound_header_candidate_count"] == 0


def test_unknown_sender_in_known_thread_does_not_become_company_reply(six_threads):
    tid = ANCHORS[0][3]
    six_threads[tid]["messages"].append(
        msg("1a14f9e381121111", tid, sender="external@unrelated.example",
            recipient=ACCOUNT, when=REPLIED_AT, labels=["INBOX"])
    )
    assert review_workspace_solar_threads(six_threads, now=NOW)["inbound_header_candidate_count"] == 0


@pytest.mark.parametrize("mutation,reason", [
    (lambda x: x.pop(ANCHORS[0][3]), "INCOMPLETE_WORKSPACE_THREAD_SCAN"),
    (lambda x: x[ANCHORS[0][3]]["messages"].clear(), "INCOMPLETE_WORKSPACE_THREAD"),
    (lambda x: x[ANCHORS[0][3]]["messages"][0].update(labelIds=["DRAFT"]), "SENT_ANCHOR_NOT_PROVED_IN_WORKSPACE"),
    (lambda x: x[ANCHORS[0][3]]["messages"][0].update(payload={"headers": [{"name":"From","value":"someone@evil.example"},{"name":"To","value":"info@gbnrg.co.uk"}]}), "SENT_ANCHOR_NOT_PROVED_IN_WORKSPACE"),
    (lambda x: x[ANCHORS[0][3]]["messages"][0].update(internalDate="1792357200000"), "UNTRUSTED_GMAIL_TIMESTAMP"),
    (lambda x: x[ANCHORS[0][3]]["messages"][0].update(threadId="aaaaaaaaaaaaaaaa"), "MESSAGE_THREAD_MISMATCH"),
    (lambda x: x[ANCHORS[0][3]]["messages"].append(deepcopy(x[ANCHORS[0][3]]["messages"][0])), "INVALID_DUPLICATE_MESSAGE_ID"),
])
def test_untrusted_missing_or_corrupt_provider_reply_scan_is_held(six_threads, mutation, reason):
    mutation(six_threads)
    with pytest.raises(EvidenceHeld, match=reason):
        review_workspace_solar_threads(six_threads, now=NOW)


class FakeService:
    def __init__(self, threads):
        self.threads_data=threads
        self.calls=[]
        self.request=None
    def users(self):
        return self
    def threads(self):
        return self
    def get(self, **kw):
        self.calls.append(kw)
        self.request=kw
        return self
    def execute(self):
        return self.threads_data[self.request["id"]]


class FakeProvider:
    def __init__(self, configured, service=None):
        self.configured=configured
        self.service=service
        self.called=False
    def _service(self):
        self.called=True
        return self.service


def test_reader_calls_exact_six_metadata_only_reads(six_threads):
    service=FakeService(six_threads)
    result=collect_workspace_solar_threads(service, now=NOW)
    assert result["verified_sent_anchors"] == 6
    assert {c["id"] for c in service.calls} == {x[3] for x in ANCHORS}
    assert all(c["format"]=="metadata" and c["userId"]=="me" for c in service.calls)
    assert all("metadataHeaders" in c and "body" not in str(c).lower() for c in service.calls)


def test_unconfigured_reader_holds_without_oauth_or_send():
    p=FakeProvider(False)
    result=run(provider=p, now=NOW)
    assert result["status"]=="HELD_WORKSPACE_READER_UNAVAILABLE"
    assert result["reason_code"]=="WORKSPACE_GMAIL_READ_SCOPE_NOT_CONFIGURED"
    assert result["source_scan_complete"] is False
    assert result["snapshot_written"] is False
    assert p.called is False


def test_fake_authorized_reader_can_validate_all_six_without_writes(six_threads):
    p=FakeProvider(True,FakeService(six_threads))
    result=run(provider=p,now=NOW)
    assert result["status"]=="WORKSPACE_SENT_ANCHORS_VERIFIED_REVIEW_ONLY"
    assert result["source_scan_complete"] is True
    assert result["verified_sent_anchors_in_live_mailbox"]==6
    assert result["snapshot_written"] is False
    assert result["database_writes"] is False
    assert result["automatic_reply_authorized"] is False


def test_fake_provider_partial_read_never_claims_any_coverage(six_threads):
    del six_threads[ANCHORS[2][3]]
    p=FakeProvider(True,FakeService(six_threads))
    result=run(provider=p,now=NOW)
    assert result["source_scan_complete"] is False
    assert result["verified_sent_anchors_in_live_mailbox"] == 0
    assert result["snapshot_written"] is False
    assert result["reason_code"]=="WORKSPACE_PROVIDER_READ_UNVERIFIED"



def test_new_reply_candidate_dedupe_and_history_are_monotonic(six_threads):
    from empire_os.workspace_solar_reply_tracking import newly_observed_workspace_replies
    prior=review_workspace_solar_threads(six_threads,now=NOW)
    assert newly_observed_workspace_replies(prior,None)==0
    assert newly_observed_workspace_replies(prior,prior)==0
    tid=ANCHORS[0][3]
    six_threads[tid]["messages"].append(
        msg("1a14f9e381121111",tid,sender="reply@gbnrg.co.uk",
            recipient=ACCOUNT,when=REPLIED_AT,labels=["INBOX"])
    )
    current=review_workspace_solar_threads(six_threads,now=NOW)
    assert newly_observed_workspace_replies(current,prior)==1
    assert newly_observed_workspace_replies(current,current)==0
    with pytest.raises(EvidenceHeld,match="PREVIOUS_INBOUND_OBSERVATION_MISSING"):
        newly_observed_workspace_replies(prior,current)


def test_previous_snapshot_wrong_sent_identity_is_denied(six_threads):
    from empire_os.workspace_solar_reply_tracking import newly_observed_workspace_replies
    current=review_workspace_solar_threads(six_threads,now=NOW)
    fake=deepcopy(current)
    fake["threads"][0]["sent_message_id"]="1a14f282abf361e5"
    with pytest.raises(EvidenceHeld,match="PREVIOUS_SENT_ANCHOR_MISMATCH"):
        newly_observed_workspace_replies(current,fake)


def test_write_mode_deduplicates_and_uses_existing_atomic_private_writer(
    six_threads,monkeypatch
):
    import scripts.poll_workspace_solar_outreach_readonly as bridge
    service=FakeService(six_threads)
    provider=FakeProvider(True,service)
    # Source-of-truth IO is mocked: no real production write.
    from pathlib import Path
    out=Path(bridge.OUTPUT)
    previous={"snapshot":None}
    def fake_exists(self):
        return False if str(self)==str(out) else Path.__dict__["exists"](self)
    writes=[]
    monkeypatch.setattr(bridge,"atomic_private_write",lambda path,obj:writes.append((path,obj)))
    result=bridge.run(provider=provider,write=True,now=NOW)
    assert result["status"]=="WORKSPACE_SENT_ANCHORS_VERIFIED_REVIEW_ONLY"
    assert result["snapshot_written"] is True
    assert result["new_inbound_header_candidates"] == 0
    assert writes and writes[0][0]==bridge.OUTPUT
    assert writes[0][1]["new_inbound_header_candidate_count"]==0
    assert "snippet" not in str(writes[0][1])
    assert "Confidential customer text" not in str(writes[0][1])
