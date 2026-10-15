"""Ops Control reply evidence is aggregate, private and never auto-promotes."""
from datetime import datetime, timezone
from pathlib import Path
import json

from empire_os.conversation_control_operational_truth import (
    inspect_conversation_evidence, SOURCE_PATHS, EXPECTED,
)
from empire_os.founder_ops_api import read_ops_snapshot

NOW=datetime(2026,10,15,12,0,tzinfo=timezone.utc)
SECRET="PRIVATE_MESSAGE_BODY_DO_NOT_DISCLOSE"

def save(root,kind,data):
    dest=root/SOURCE_PATHS[kind]
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(data),encoding="utf-8")

def set_up(root):
    controls={key:{
        "control":key,"lane":"conversations_replies",
        "status":"VERIFIED_RUNTIME" if key in
          {"action_authority","duplicate_detection","freshness","input_quality","quarantine"}
          else "UNVERIFIED",
        "reason":SECRET,"action_authority_granted":False,
    } for key in EXPECTED}
    save(root,"bindings",{"authority":"OBSERVE","lanes":[
        {"lane":"conversations_replies","controls":controls}]})
    save(root,"collector",{
        "mode":"OBSERVE","canonical_messages":[{"body":SECRET}],
        "semantic_effectiveness":{
            "candidate_count":5,"canonical_message_count":0,
            "inbound_reply_count":0,"outcome_link_count":0,
        },
        "source_admission":{
            "admitted_conversation_candidate_rows":5,
            "tenant_binding_established":False,
        },
    })
    save(root,"health",{"status":"READ_SUCCESS","secret":SECRET})
    save(root,"linkage",{
        "mode":"OBSERVE","verification_status":"SCHEMA_PATH_FOUND_DATA_PROOF_REQUIRED",
        "actual_joined_rows_proven":0,
        "blockers":[
            "JOIN_CARDINALITY_UNVERIFIED",
            "TENANT_AUTHORITY_BINDING_NOT_PROVEN",
            SECRET,
        ],
    })
    save(root,"identity_discovery",{"generated_at":"2026-10-07T15:35:27+00:00"})
    save(root,"identity_gap",{"generated_at":"2026-10-07T15:52:10+00:00"})


def test_realistic_six_control_gap_without_private_payload(tmp_path):
    set_up(tmp_path)
    report=inspect_conversation_evidence(tmp_path,now=NOW)
    assert report["status"]=="HOLD_REAL_REPLY_EVIDENCE_REQUIRED"
    assert report["canonical_control_schema_verified"] is True
    assert report["verified_control_count"]==5
    assert report["total_control_count"]==11
    assert set(report["unverified_controls"])=={
        "canonical_identity","conflict_detection","entity_classification",
        "evidence_lineage","outcome_linkage","output_quality"}
    assert report["original_candidate_count"]==5
    assert report["canonical_message_count"]==0
    assert report["observed_inbound_reply_candidate_count"]==0
    assert report["authenticated_inbound_reply_count_verified"] is None
    assert report["verified_reply_join_count"]==0
    assert report["tenant_binding_claimed_in_collector"] is False
    assert report["tenant_binding_independently_verified"] is False
    assert report["collector_source_read_verified"] is True
    assert len(report["stale_identity_metadata_sources"])==2
    assert "JOIN_CARDINALITY_UNVERIFIED" in report["source_blockers"]
    assert SECRET not in json.dumps(report)
    for key in ("outbound_enabled","customer_delivery_enabled","payment_execution",
                "database_writes","buyer_intent_verified","automatic_promotion_authorized"):
        assert report[key] is False


def test_missing_or_corrupted_sources_stay_on_hold(tmp_path):
    empty=inspect_conversation_evidence(tmp_path,now=NOW)
    assert empty["canonical_control_schema_verified"] is False
    assert empty["verified_control_count"]==0
    assert len(empty["unverified_controls"])==11
    assert empty["canonical_message_count"] is None
    assert "LIVE_COLLECTOR_OR_LINKAGE_NOT_READY" in empty["source_blockers"]
    save(tmp_path,"bindings",{"authority":"SEND","lanes":[]})
    invalid=inspect_conversation_evidence(tmp_path,now=NOW)
    assert invalid["automatic_promotion_authorized"] is False
    assert invalid["canonical_control_schema_verified"] is False


def test_stale_evidence_does_not_become_verified_on_new_snapshot(tmp_path):
    set_up(tmp_path)
    report=inspect_conversation_evidence(tmp_path,
        now=datetime(2026,10,16,12,tzinfo=timezone.utc))
    assert set(report["stale_identity_metadata_sources"])=={
        "identity_discovery","identity_gap"}
    assert report["authenticated_reply_identity_verified"] is False
    assert report["buyer_intent_verified"] is False


def test_existing_founder_ops_endpoint_surfaces_private_safe_aggregates(tmp_path):
    set_up(tmp_path)
    report=inspect_conversation_evidence(tmp_path,now=NOW)
    snapshot=tmp_path/"runtime/ops_control/latest.json"
    snapshot.parent.mkdir(parents=True,exist_ok=True)
    snapshot.write_text(json.dumps({
        "schema_version":"empire.ops_control_cycle.v1",
        "conversation_evidence_review":report,
        "health_domains":{"conversation_evidence":report["status"]},
    }))
    rendered=read_ops_snapshot(snapshot)
    assert rendered["available"] is True
    assert rendered["conversation_evidence_review"]["verified_control_count"]==5
    assert SECRET not in json.dumps(rendered)


def test_ops_control_reuses_existing_owner_no_new_service():
    script=Path("scripts/run_ops_control_cycle.py").read_text()
    assert "inspect_conversation_evidence(Path" in script
    assert '"conversation_evidence_review": conversation_evidence_review' in script
    assert '"conversation_evidence": conversation_evidence_review["status"]' in script
    observer=Path("empire_os/conversation_control_operational_truth.py").read_text()
    for forbidden in ("systemctl start","systemctl restart","send_email(",
                      "execute_plan(","os.environ["):
        assert forbidden not in observer


def test_quarantine_counts_are_allowlisted_aggregate_only(tmp_path):
    set_up(tmp_path)
    path=tmp_path/SOURCE_PATHS["collector"]
    data=json.loads(path.read_text())
    data["quarantine"]={"records":[
        {"source_record_id":SECRET,"reasons":[
            "MISSING_STABLE_THREAD_ID",
            "MISSING_CANONICAL_CONTACT_IDENTITY",
        ]},
        {"source_record_id":SECRET,"reasons":[
            "MISSING_STABLE_MESSAGE_ID",
            "MISSING_CANONICAL_CONTACT_IDENTITY",
        ]},
    ]}
    path.write_text(json.dumps(data))
    report=inspect_conversation_evidence(tmp_path,now=NOW)
    assert report["quarantined_candidate_count"]==2
    assert report["safe_quarantine_reason_counts"]=={
        "MISSING_CANONICAL_CONTACT_IDENTITY":2,
        "MISSING_STABLE_MESSAGE_ID":1,
        "MISSING_STABLE_THREAD_ID":1,
    }
    assert report["quarantine_reason_coverage_complete"] is True
    assert SECRET not in json.dumps(report)
    assert report["authenticated_reply_identity_verified"] is False


def test_unknown_quarantine_reason_never_disclosed_or_marked_complete(tmp_path):
    set_up(tmp_path)
    path=tmp_path/SOURCE_PATHS["collector"]
    data=json.loads(path.read_text())
    data["quarantine"]={"records":[{
        "source_record_id":SECRET,
        "reasons":["PRIVATE_PERSON_NAME_DO_NOT_EMIT"],
    }]}
    path.write_text(json.dumps(data))
    report=inspect_conversation_evidence(tmp_path,now=NOW)
    assert report["quarantine_reason_coverage_complete"] is False
    assert report["quarantined_candidate_count"] is None
    assert all(x is None for x in report["safe_quarantine_reason_counts"].values())
    assert "PRIVATE_PERSON_NAME" not in json.dumps(report)


def test_unavailable_owned_mailbox_is_an_explicit_safe_hold(tmp_path):
    set_up(tmp_path)
    save(tmp_path,"mailbox_observer",{
        "schema_version":"empire-founder-mailbox-inprocess-observer-v1",
        "generated_at":"2026-10-15T11:59:00+00:00",
        "mode":"OBSERVE","status":"OBSERVER_ERROR",
        "error_type":"HTTPException",
        "error":"503: mailbox_provider_unavailable:MailboxReadUnavailable "
                + SECRET,
        "outbound":False,"db_write":False,"mailbox_write":False,
    })
    report=inspect_conversation_evidence(tmp_path,now=NOW)
    assert report["founder_mailbox_observer_status"]=="OBSERVER_ERROR"
    assert report["founder_mailbox_observer_metadata_stale"] is False
    assert report["founder_mailbox_observer_proves_authenticated_reply"] is False
    assert "FOUNDER_MAILBOX_READ_UNAVAILABLE" in report["source_blockers"]
    assert report["buyer_intent_verified"] is False
    assert report["automatic_promotion_authorized"] is False
    assert SECRET not in json.dumps(report)
    assert "mailbox_provider_unavailable" not in json.dumps(report)


def test_missing_and_stale_mailbox_observation_do_not_fabricate_replies(tmp_path):
    set_up(tmp_path)
    missing=inspect_conversation_evidence(tmp_path,now=NOW)
    assert missing["founder_mailbox_observer_status"]=="NOT_VERIFIED"
    assert "FOUNDER_MAILBOX_OBSERVER_NOT_CURRENTLY_VERIFIED" in missing["source_blockers"]
    save(tmp_path,"mailbox_observer",{
        "generated_at":"2026-10-06T09:00:00+00:00",
        "status":"NO_COMPLETE_INBOUND_MESSAGE",
        "observed":0,
    })
    stale=inspect_conversation_evidence(tmp_path,now=NOW)
    assert stale["founder_mailbox_observer_status"]=="NO_COMPLETE_INBOUND_MESSAGE"
    assert stale["founder_mailbox_observer_metadata_stale"] is True
    assert "FOUNDER_MAILBOX_OBSERVER_NOT_CURRENTLY_VERIFIED" in stale["source_blockers"]
    assert stale["authenticated_inbound_reply_count_verified"] is None
