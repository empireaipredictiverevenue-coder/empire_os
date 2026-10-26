"""V11: isolated original Workspace heat-pump reply observer, no live Gmail."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import stat

import pytest

from empire_os.workspace_heat_pump_reply_tracking import (
    ANCHORS, EXPECTED, collect_heat_pump_threads,
    newly_observed_heat_pump_candidates, review_heat_pump_threads,
)
from empire_os.workspace_solar_reply_tracking import EvidenceHeld

NOW = datetime(2026, 10, 26, 18, 0, tzinfo=timezone.utc)
MILLIS = str(int(datetime(2026, 10, 25, 1, 18, tzinfo=timezone.utc).timestamp()*1000))
INBOUND = str(int(datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc).timestamp()*1000))
SENDER = "phil@mail.empire-ai.co.uk"
PARTNER = "partner@example-partner.co.uk"


def msg(mid, tid, sender, recipient, stamp, labels, **headers):
    values = {
        "From": sender, "To": recipient,
        "Message-ID": headers.get("message_id", "<" + mid + "@example.test>"),
    }
    if "reply_to" in headers:
        values["In-Reply-To"] = headers["reply_to"]
    return {
        "id": mid, "threadId": tid, "internalDate": stamp,
        "labelIds": labels,
        "payload": {"headers": [{"name": k, "value": v}
                                for k,v in values.items()]},
    }


def make_threads():
    data = {}
    for _, tid, anchor in ANCHORS:
        data[tid] = {
            "id": tid,
            "messages": [msg(anchor, tid, SENDER, PARTNER, MILLIS, ["SENT"])],
        }
    return data


def inbound(data, *, partner=PARTNER, to=SENDER, at=INBOUND,
            mid="1a99999999999999", thread_index=0):
    _, tid, anchor = ANCHORS[thread_index]
    data[tid]["messages"].append(
        msg(mid, tid, partner, to, at, ["INBOX"],
            reply_to="<" + anchor + "@example.test>")
    )
    return mid


def review(data):
    return review_heat_pump_threads(data, now=NOW)


def test_four_existing_sends_only_not_buyers():
    observation = review(make_threads())
    assert observation["monitored_threads"] == len(ANCHORS) == 4
    assert observation["verified_original_sends"] == 4
    assert observation["inbound_header_candidate_count"] == 0
    assert not observation["message_bodies_or_subjects_retained"]
    for name in ("commercial_buyer_acceptance_verified",
                 "payment_reconciled", "economic_memory_authorized",
                 "outbound_sent", "database_writes", "automatic_reply_authorized"):
        assert observation[name] is False
    assert newly_observed_heat_pump_candidates(observation, None) == 0


def test_exact_reply_is_only_header_candidate_and_replay_not_new():
    d = make_threads()
    mid = inbound(d)
    got = review(d)
    c = got["threads"][0]["inbound_header_candidates"][0]
    assert c["gmail_message_id"] == mid
    assert c["rfc_parent_relation"] == "DIRECT_PARENT_MATCH"
    assert c["sender_correspondence"] == "EXACT_ORIGINAL_RECIPIENT"
    assert c["status"] == "HEADER_CANDIDATE_HUMAN_VERIFICATION_REQUIRED"
    assert got["commercial_buyer_acceptance_verified"] is False
    assert newly_observed_heat_pump_candidates(got, None) == 1
    assert newly_observed_heat_pump_candidates(got, deepcopy(got)) == 0


def test_same_domain_colleague_header_candidate_never_commercial_authority():
    d = make_threads()
    inbound(d, partner="colleague@example-partner.co.uk")
    got = review(d)
    assert got["inbound_header_candidate_count"] == 1
    assert got["threads"][0]["inbound_header_candidates"][0][
        "sender_correspondence"] == "SAME_DOMAIN_DIFFERENT_ADDRESS"
    assert got["threads"][0]["buyer_terms_verified"] is False


@pytest.mark.parametrize("partner,to", [
    ("spam@other.example", SENDER),
    (SENDER, SENDER),
    (PARTNER, "not-our-mailbox@example.com"),
])
def test_wrong_sender_or_reply_destination_not_accepted(partner,to):
    d = make_threads()
    inbound(d, partner=partner, to=to)
    assert review(d)["inbound_header_candidate_count"] == 0


@pytest.mark.parametrize("change,code", [
    (lambda d: d.pop(ANCHORS[1][1]), "ANCHOR_COVERAGE"),
    (lambda d: d[ANCHORS[0][1]]["messages"].clear(), "MESSAGES_INCOMPLETE"),
    (lambda d: d[ANCHORS[0][1]]["messages"][0].update(labelIds=["DRAFT"]), "ANCHOR_UNVERIFIED"),
    (lambda d: d[ANCHORS[0][1]]["messages"][0].update(threadId="fake"), "WRONG_THREAD"),
    (lambda d: d[ANCHORS[0][1]]["messages"].append(
        deepcopy(d[ANCHORS[0][1]]["messages"][0])), "DUPLICATE"),
    (lambda d: d[ANCHORS[0][1]]["messages"][0].update(
        internalDate="1888888888888"), "TIMESTAMP"),
])
def test_untrusted_incomplete_or_duplicate_provider_threads_fail_closed(change,code):
    d=make_threads()
    change(d)
    with pytest.raises(EvidenceHeld, match=code):
        review(d)


def test_late_outcome_evidence_cannot_be_silently_erased():
    d = make_threads()
    inbound(d)
    prior = review(d)
    now = review(make_threads())
    with pytest.raises(EvidenceHeld, match="CANDIDATE_DROPPED"):
        newly_observed_heat_pump_candidates(now, prior)


def test_spoofed_previous_evidence_or_scope_rejected():
    d = make_threads()
    current=review(d)
    for mutate in (
        lambda x: x.update(schema_version="invented"),
        lambda x: x.update(outbound_sent=True),
        lambda x: x["threads"][0].update(
            original_sent_message_id=ANCHORS[1][2]),
        lambda x: x["threads"][0].update(inbound_header_candidates=[
            {"gmail_message_id": "not-a-gmail-id", "status": "HEADER_CANDIDATE_HUMAN_VERIFICATION_REQUIRED"}]),
    ):
        previous = deepcopy(current)
        mutate(previous)
        with pytest.raises(EvidenceHeld):
            newly_observed_heat_pump_candidates(current, previous)


class FakeReq:
    def __init__(self,value):self.value=value
    def execute(self):return deepcopy(self.value)


class FakeService:
    def __init__(self, records):
        self.records=records
        self.accessed=[]
    def users(self):return self
    def threads(self):return self
    def get(self, *, userId, id, format, metadataHeaders):
        self.accessed.append((userId,id,format,tuple(metadataHeaders)))
        return FakeReq(self.records[id])


def test_existing_gmail_metadata_client_only_four_exact_threads():
    service=FakeService(make_threads())
    result=collect_heat_pump_threads(service, now=NOW)
    assert result["verified_original_sends"]==4
    assert {item[1] for item in service.accessed}==EXPECTED
    assert all(item[2]=="metadata" and item[0]=="me"
               for item in service.accessed)


def test_existing_solar_observer_is_preserved_with_optional_heat_cohort(monkeypatch):
    import scripts.poll_workspace_solar_outreach_readonly as poll
    original=make_threads()
    service=FakeService(original)
    class Provider:
        configured=True
        def _service(self):return service
    monkeypatch.setattr(poll,"collect_workspace_solar_threads",lambda *a,**kw:{
        "verified_sent_anchors":6, "monitored_threads":6,
        "inbound_header_candidate_count":0})
    result=poll.run(provider=Provider(),write=False,now=NOW)
    assert result["source_scan_complete"] is True
    assert result["verified_sent_anchors_in_live_mailbox"] == 6
    assert result["heat_pump_verified_sent_anchors"] == 4
    assert result["heat_pump_inbound_header_candidates"] == 0
    assert result["heat_pump_snapshot_written"] is False
    assert result["automatic_reply_authorized"] is False


def test_heat_provider_failure_keeps_original_solar_cohort_healthy(monkeypatch):
    import scripts.poll_workspace_solar_outreach_readonly as poll
    class Provider:
        configured=True
        def _service(self):return object()
    monkeypatch.setattr(poll,"collect_workspace_solar_threads",lambda *a,**kw:{
        "verified_sent_anchors":6, "monitored_threads":6,
        "inbound_header_candidate_count":0})
    result=poll.run(provider=Provider(),write=False,now=NOW)
    assert result["source_scan_complete"] is True
    assert result["heat_pump_status"]=="HELD_HEAT_PUMP_REPLY_REVIEW_UNAVAILABLE"


def test_private_write_is_idempotent_and_preserves_candidate(monkeypatch,tmp_path):
    import scripts.poll_workspace_solar_outreach_readonly as poll
    original = make_threads()
    inbound(original)
    service=FakeService(original)
    class Provider:
        configured=True
        def _service(self):return service
    monkeypatch.setattr(poll,"collect_workspace_solar_threads",lambda *a,**kw:{
        "verified_sent_anchors":6, "monitored_threads":6,
        "inbound_header_candidate_count":0})
    monkeypatch.setattr(poll,"newly_observed_workspace_replies",lambda *a,**kw:0)
    monkeypatch.setattr(poll,"OUTPUT",tmp_path/"solar.json")
    monkeypatch.setattr(poll,"HEAT_OUTPUT",tmp_path/"heat.json")
    first=poll.run(provider=Provider(),write=True,now=NOW,
                   output=tmp_path/"solar.json")
    assert first["heat_pump_snapshot_written"] is True
    assert first["heat_pump_new_inbound_candidates"]==1
    second=poll.run(provider=Provider(),write=True,now=NOW,
                    output=tmp_path/"solar.json")
    assert second["heat_pump_new_inbound_candidates"]==0
    assert stat.S_IMODE((tmp_path/"heat.json").stat().st_mode)==0o600
    payload=json.loads((tmp_path/"heat.json").read_text())
    assert payload["inbound_header_candidate_count"]==1
    assert not any(k in payload for k in ("body","snippet","subject","raw"))
