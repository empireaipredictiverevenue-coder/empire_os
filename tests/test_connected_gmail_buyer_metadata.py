from copy import deepcopy
from datetime import datetime, timedelta, timezone
import pytest
from empire_os.commercial_relationship_registry import RelationshipEvidenceError, reconcile
from scripts.import_connected_gmail_buyer_metadata import THREADS, refreshed_summary

NOW=datetime(2026,10,10,12,0,tzinfo=timezone.utc)
NAMES={"lead-smart":"Lead Smart","leadbank":"LeadBank",
"validated":"Validated / Home Services Lead Group","connexis":"Connexis"}
DOMAINS={"lead-smart":"leadsmartinc.com","leadbank":"alliancevs.io",
"validated":"validatedlg.ai","connexis":"connex.is"}

def inputs():
    old={"schema_version":"empire.buyer_mail_relationship_summary.v1",
         "origin":"connected_gmail_connector_read_only","mailbox":"flavag83@gmail.com",
         "captured_at":"2026-10-01T12:00:00Z","threads":[]}
    index={"schema_version":"empire.buyer_gmail_original_message_index.v1",
           "source":"connected_gmail_connector_read_only",
           "collected_at":"2026-10-10T11:59:40Z","threads":[]}
    for i,(thread,key) in enumerate(THREADS.items()):
        old["threads"].append({
           "gmail_thread_id":thread,"entity_key":key,"company":NAMES[key],
           "identity_domains":[DOMAINS[key]],"last_inbound_at":None,
           "last_inbound_message_id":None,"last_outbound_at":None,
           "last_outbound_message_id":None,"next_action_code":"REVIEW_ONLY",
           "bounced_addresses":[]})
        messages=[
          {"id":f"{i+1:016x}","date":"2026-10-10T11:02:00",
           "from":"Phil <flavag83@gmail.com>","labels":["SENT"]},
          {"id":f"{i+101:016x}","date":"2026-10-10T11:42:00",
           "from":f"Buyer <reply@{DOMAINS[key]}>","labels":["INBOX"]}]
        index["threads"].append({
           "thread_id":thread,"partner":NAMES[key],
           "truncated":False,"message_count":2,"messages":messages})
    old["threads"].append({
      "gmail_thread_id":"abcdef1234567890","entity_key":"historical-other",
      "company":"Historical Other","identity_domains":["example.com"],
      "last_inbound_at":None,"last_inbound_message_id":None,
      "last_outbound_at":"2026-10-01T13:00:00Z",
      "last_outbound_message_id":"eeeeeeeeeeeeeeee",
      "next_action_code":"REVIEW_ONLY","bounced_addresses":[]})
    return old,index

def test_import_updates_only_four_and_preserves_historical_staleness():
    old,index=inputs();before=deepcopy(old)
    result,summary=refreshed_summary(old,index,now=NOW)
    assert old==before
    assert result["captured_at"]==before["captured_at"]
    assert len(result["threads"])==5
    assert len(result["partial_updated_thread_ids"])==4
    assert summary["new_history_directions"]==8
    assert summary["outbound_authorized"] is False
    q=reconcile(result,{"candidate_count":0,"candidates":[]},
                {"shortlisted_count":0,"targets":[]},now=NOW)
    assert q["gmail_snapshot_fresh"] is False
    assert q["partial_gmail_thread_count_fresh"]==4
    rows={x["entity_key"]:x for x in q["relationships"]}
    assert all(rows[k]["gmail_snapshot_fresh"] for k in NAMES)
    assert not rows["historical-other"]["gmail_snapshot_fresh"]
    assert not q["automatic_live_gmail_ingest_configured"]
    assert not q["outbound_authorized"]

def test_fake_sender_is_not_classed_buyer_reply():
    old,index=inputs()
    index["threads"][0]["messages"][-1]["from"]="Someone <contact@unknown.example>"
    result,_=refreshed_summary(old,index,now=NOW)
    assert result["threads"][0]["last_inbound_message_id"] is None

def test_spam_delivery_error_does_not_become_reply():
    old,index=inputs()
    index["threads"][2]["messages"][-1].update(from_="mailer-daemon@somewhere.example",labels=["SPAM"])
    result,_=refreshed_summary(old,index,now=NOW)
    assert result["threads"][2]["last_inbound_message_id"] is None

@pytest.mark.parametrize("mutation",[
    lambda x:x["threads"].pop(),
    lambda x:x["threads"][0].update(truncated=True),
    lambda x:x["threads"][0].update(message_count=3),
    lambda x:x["threads"][0]["messages"][0].update(id="BAD"),
    lambda x:x["threads"][0].update(partner="Wrong buyer"),
    lambda x:x.update(source="unknown"),
    lambda x:x.update(collected_at="2026-10-01T12:00:00Z"),
])
def test_incomplete_or_untrusted_scan_blocked(mutation):
    old,index=inputs();before=deepcopy(old)
    mutation(index)
    with pytest.raises((RelationshipEvidenceError,ValueError)):
        refreshed_summary(old,index,now=NOW)
    assert old==before

def test_history_must_not_rewind():
    old,index=inputs()
    old["threads"][0]["last_outbound_at"]="2026-10-10T11:55:00Z"
    old["threads"][0]["last_outbound_message_id"]="9999999999999999"
    with pytest.raises(RelationshipEvidenceError,match="REWIND"):
        refreshed_summary(old,index,now=NOW)

def test_partial_evidence_expires_without_new_scan():
    old,index=inputs();updated,_=refreshed_summary(old,index,now=NOW)
    q=reconcile(updated,{"candidate_count":0,"candidates":[]},
                {"shortlisted_count":0,"targets":[]},
                now=NOW+timedelta(days=5))
    assert q["partial_gmail_thread_count_fresh"]==0
    assert not any(x["gmail_snapshot_fresh"] for x in q["relationships"])


def test_raw_email_body_rejected_at_connector_boundary():
    old,index=inputs()
    index["threads"][0]["messages"][0]["body"]="Do not copy private emails"
    with pytest.raises(RelationshipEvidenceError,match="RAW_MAIL"):
        refreshed_summary(old,index,now=NOW)



def test_unbracketed_provider_sender_metadata_updates_latest_sent_history():
    old,index=inputs()
    target=index["threads"][0]
    target["messages"][-1]["from"]="Buyer Name reply@leadsmartinc.com"
    target["messages"][0]["from"]="Phil Livesley flavag83@gmail.com"
    result,summary=refreshed_summary(old,index,now=NOW)
    row=next(x for x in result["threads"] if x["entity_key"]=="lead-smart")
    assert row["last_outbound_message_id"]==target["messages"][0]["id"]
    assert row["last_inbound_message_id"]==target["messages"][-1]["id"]
    assert summary["new_history_directions"]==8


def test_multi_address_or_injected_sender_cannot_be_treated_as_known_buyer():
    from scripts.import_connected_gmail_buyer_metadata import _addr
    assert _addr("Two addresses kieran@connex.is fake@connex.is")==""
    assert _addr("Kieran kieran@connex.is\r\nReply-To: fake@evil.example")==""
    assert _addr("Director kieran@connex.is")=="kieran@connex.is"
    assert _addr("From <KIERAN@CONNEX.IS>")=="kieran@connex.is"


def test_first_party_readonly_gmail_source_is_accepted_without_outbound_authority():
    old, index = inputs()
    index["source"] = "empire_gmail_api_readonly"
    updated, summary = refreshed_summary(old, index, now=NOW)
    assert summary["outbound_authorized"] is False
    assert summary["known_threads_checked"] == 4
    assert len(updated["partial_updated_thread_ids"]) == 4
    assert updated["captured_at"] == old["captured_at"]
    assert all(item["gmail_thread_id"] in THREADS for item in updated["threads"][:4])
