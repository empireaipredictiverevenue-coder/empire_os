"""Full buyer setup request is asked once; no automatic duplicate sends."""
from datetime import datetime, timedelta, timezone
import pytest
from empire_os.commercial_relationship_registry import PARTNER_PILOT_SCOPES, reconcile

NOW = datetime(2026,10,9,23,45,tzinfo=timezone.utc)

def source(key, domain, message_id):
    return {
      "schema_version":"empire.buyer_mail_relationship_summary.v1",
      "origin":"connected_gmail_connector_read_only",
      "mailbox":"flavag83@gmail.com",
      "captured_at":"2026-10-09T23:35:00Z",
      "threads":[{
        "entity_key":key, "company":key,
        "identity_domains":[domain],
        "gmail_thread_id":PARTNER_PILOT_SCOPES[key]["reviewed_thread"],
        "last_inbound_at":"2026-10-09T18:00:00Z",
        "last_inbound_message_id":"abcdef1234567890",
        "last_outbound_at":"2026-10-09T23:25:00Z",
        "last_outbound_message_id":message_id,
        "bounced_addresses":[],
        "next_action_code":"ONBOARDING_BUYBOX",
      }],
    }

def project(src, now=NOW):
    return reconcile(
      src,
      {"candidate_count":0,"candidates":[],"generated_at":NOW.isoformat()},
      {"shortlisted_count":0,"targets":[]},
      now=now,
    )["partner_pilot_readiness_queue"][0]

@pytest.mark.parametrize("key,domain,msg",[
  ("leadbank","alliancevs.io","1a122fc6010e3b5b"),
  ("validated","validatedlg.ai","1a122fc70c9614c1"),
  ("connexis","connex.is","1a122fc85a098bea"),
])
def test_all_six_groups_already_requested_in_verified_thread(key,domain,msg):
    row=project(source(key,domain,msg))
    d=row["single_pass_buyer_intake"]
    assert d["past_full_information_request_proven_in_import"] is True
    assert d["last_full_request_evidence_ref"]=="gmail:"+msg
    assert len(d["question_groups"])==6
    assert d["next_action"]=="WAIT_PARTNER_ANSWERS_NO_DUPLICATE_REQUEST"
    assert not d["outbound_authorized"]
    assert not d["contract_authorized"]
    assert not d["traffic_authorized"]
    assert not d["buyer_buybox_verified"]
    assert not d["buyer_terms_verified"]
    assert row["gate_count_verified"]==0

def test_unknown_outbound_cannot_fabricate_previous_request_or_send():
    row=project(source("leadbank","alliancevs.io","1234567890abcdef"))
    d=row["single_pass_buyer_intake"]
    assert not d["past_full_information_request_proven_in_import"]
    assert d["last_full_request_evidence_ref"] is None
    assert d["next_action"]=="RECONCILE_EXISTING_EMAIL_HISTORY_BEFORE_ASKING"
    assert d["outbound_authorized"] is False
    assert row["outbound_authorized"] is False

def test_stale_import_never_promotes_sent_request_into_authority():
    row=project(source("connexis","connex.is","1a122fc85a098bea"),
                NOW+timedelta(days=7))
    d=row["single_pass_buyer_intake"]
    assert d["past_full_information_request_proven_in_import"] is True
    assert d["source_snapshot_fresh"] is False
    assert d["next_action"]=="WAIT_PARTNER_ANSWERS_NO_DUPLICATE_REQUEST"
    assert d["outbound_authorized"] is False
    assert row["gate_count_verified"]==0
