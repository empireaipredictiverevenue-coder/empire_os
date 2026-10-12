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
    # Latest import cannot prove the original send by itself, but the
    # reviewed original Gmail message is still bound to this exact thread.
    assert d["past_full_request_known_from_reviewed_history"] is True
    assert d["last_full_request_evidence_ref"]=="gmail:1a122fc6010e3b5b"
    assert d["next_action"]=="WAIT_PARTNER_ANSWERS_NO_DUPLICATE_REQUEST"
    assert d["repeat_full_request_blocked"] is True
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


@pytest.mark.parametrize("key,domain,original,later", [
  ("leadbank","alliancevs.io","1a122fc6010e3b5b","abcd1234abcd1234"),
  ("validated","validatedlg.ai","1a122fc70c9614c1","abcd1234abcd1234"),
  ("connexis","connex.is","1a122fc85a098bea","abcd1234abcd1234"),
])
def test_immutable_full_request_blocks_new_questionnaire_after_later_message(
        key, domain, original, later):
    # Later send in the SAME partner thread does not erase reviewed request.
    row=project(source(key,domain,later))
    d=row["single_pass_buyer_intake"]
    assert d["past_full_information_request_proven_in_import"] is False
    assert d["past_full_request_known_from_reviewed_history"] is True
    assert d["last_full_request_evidence_ref"]=="gmail:"+original
    assert d["repeat_full_request_blocked"] is True
    assert d["repeat_block_reason"]=="PRIOR_COMPLETE_REQUEST_IN_REVIEWED_THREAD"
    assert d["next_action"]=="WAIT_PARTNER_ANSWERS_NO_DUPLICATE_REQUEST"
    assert d["outbound_authorized"] is False


def test_unrelated_thread_cannot_inherit_reviewed_request_evidence():
    data=source("validated","validatedlg.ai","abcdefabcdefabcd")
    data["threads"][0]["gmail_thread_id"]="fedcbafedcbafedc"
    row=project(data)
    status=row["single_pass_buyer_intake"]
    assert not status["past_full_request_known_from_reviewed_history"]
    assert status["last_full_request_evidence_ref"] is None
    assert status["repeat_full_request_blocked"]
    assert status["next_action"]=="RECONCILE_EXISTING_EMAIL_HISTORY_BEFORE_ASKING"


def test_lead_smart_reviewed_delta_is_already_sent_not_another_questionnaire():
    from empire_os.commercial_relationship_registry import reviewed_request_duplicate_guard
    d=reviewed_request_duplicate_guard("lead-smart",{
        "gmail_thread_ids":["1a0d9ce883c87d4a"],
        "last_outbound_message_id":"1a12d06897ca9ac3",
        "gmail_snapshot_fresh":False,
    })
    assert d["status"]=="SPECIFIC_ROUTING_RECORDING_REQUEST_ALREADY_SENT"
    assert d["request_provenance"]=="gmail:1a12d47934923a1d"
    assert not d["last_outbound_is_independent_proof_of_send"]
    assert len(d["outstanding_buyer_questions"])==2
    assert d["repeat_full_request_allowed"] is False
    assert d["outbound_authorized"] is False


def test_unrelated_or_wrong_thread_cannot_inherit_lead_smart_request():
    from empire_os.commercial_relationship_registry import reviewed_request_duplicate_guard
    d=reviewed_request_duplicate_guard("lead-smart",{
        "gmail_thread_ids":["1a0cfb65e0dd960e"],
        "last_outbound_message_id":"1a12d47934923a1d",
    })
    assert d["status"]=="THREAD_RECONCILIATION_REQUIRED"
    assert d["request_provenance"] is None
    assert not d["outbound_authorized"]
    other=reviewed_request_duplicate_guard("unknown-buyer",{
        "gmail_thread_ids":["1a0d9ce883c87d4a"]})
    assert other["status"]=="UNREVIEWED_RELATIONSHIP"
    assert not other["repeat_full_request_allowed"]


def test_lead_smart_relationship_row_exposes_blocked_duplicate_request():
    from empire_os.commercial_relationship_registry import reconcile
    from datetime import datetime,timezone
    now=datetime(2026,10,12,9,0,tzinfo=timezone.utc)
    report=reconcile({
        "schema_version":"empire.buyer_mail_relationship_summary.v1",
        "origin":"connected_gmail_connector_read_only",
        "mailbox":"flavag83@gmail.com",
        "captured_at":"2026-10-12T08:59:00Z",
        "threads":[{
            "entity_key":"lead-smart","company":"Lead Smart",
            "identity_domains":["leadsmartinc.com"],
            "gmail_thread_id":"1a0d9ce883c87d4a",
            "last_inbound_at":"2026-10-11T23:20:44Z",
            "last_inbound_message_id":"1a12d44d7e2f46a8",
            "last_outbound_at":"2026-10-11T23:21:44Z",
            "last_outbound_message_id":"1a12d47934923a1d",
            "bounced_addresses":[],"next_action_code":"LANDING_APPROVAL_AND_ROUTE_PROOF",
        }]
    },{"candidate_count":0,"candidates":[]},
       {"shortlisted_count":0,"targets":[]},
       now=now,do_not_pursue_domains=frozenset())
    r=report["relationships"][0]
    guard=r["buyer_onboarding_duplicate_guard"]
    assert guard["request_provenance"]=="gmail:1a12d47934923a1d"
    assert guard["outbound_authorized"] is False
    assert guard["repeat_full_request_allowed"] is False
    assert len(guard["outstanding_buyer_questions"])==2
