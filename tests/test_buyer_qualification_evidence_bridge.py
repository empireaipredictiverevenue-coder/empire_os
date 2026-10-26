"""Original buyer pilot requirements are joined by canonical identity and thread."""
import json
from datetime import datetime, timedelta, timezone

from empire_os.buyer_qualification_evidence_bridge import load_registry, match_partner_buyboxes

NOW = datetime(2026, 10, 26, 19, 30, tzinfo=timezone.utc)


def record(global_fresh=False):
    return {
        "schema_version": "empire.commercial_relationship_registry.v1",
        "generated_at": NOW.isoformat(), "mode": "OBSERVE",
        "execution_authority": "NONE",
        "outbound_authorized": False, "outbound_sent": False,
        "next_actions_automatic_sends": False,
        "founder_actions_are_draft_only": True,
        "partner_pilot_readiness_is_activation_authority": False,
        "gmail_snapshot_fresh": global_fresh,
        "relationships": [
            {"entity_key": "existing-partner",
             "identity_domains": ["buyerco.com"], "gmail_thread_ids": ["1a0cfb65e0dd960e"],
             "do_not_pursue": False,
             "outbound_authorized": False, "commercial_buyer_approved": False,
             "gmail_snapshot_fresh": True, "stage": "AWAITING_BUYER"},
        ],
        "partner_pilot_readiness_queue": [
            {"entity_key": "existing-partner",
             "reviewed_gmail_thread_id": "1a0cfb65e0dd960e",
             "mailbox_snapshot_fresh": True,
             "activation_gates": {
                 "buyer_buybox_received_and_verified": False,
                 "current_target_geography_verified": False},
             "single_pass_buyer_intake": {
                 "execution_authority": "NONE",
                 "outbound_authorized": False,
                 "repeat_full_request_blocked": True,
                 "next_action": "WAIT_PARTNER_ANSWERS_NO_DUPLICATE_REQUEST"},
             "execution_authority": "NONE", "outbound_authorized": False,
             "live_traffic_authorized": False,
             "partner_requirement_evidence_requested": [
                 "active_roofing_zips_and_buyer_markets",
                 "accepted_jobs_and_qualified_billable_event"]},
        ],
    }


def test_historical_partner_buybox_is_review_only_no_duplicate_request():
    source=record()
    matches=match_partner_buyboxes(source, allowed_domains={"buyerco.com"},
                                  source_state="PARTIAL_GMAIL_SNAPSHOT_REVIEW_ONLY")
    assert set(matches) == {"buyerco.com"}
    outcome=matches["buyerco.com"]
    assert outcome["source_state"] == "HISTORICAL_THREAD_CONTEXT_SOURCE_REFRESH_REQUIRED"
    assert outcome["full_request_already_known"] is True
    assert outcome["geography_independently_verified"] is False
    assert outcome["buyer_pilot_qualified"] is False
    assert outcome["automatic_followup_authorized"] is False
    assert outcome["outstanding_requirement_count"] == 2


def test_fresh_snapshot_remains_requirements_pending_not_acceptance():
    source=record(True)
    result=match_partner_buyboxes(source, allowed_domains={"buyerco.com"},
                                  source_state="CURRENT_REGISTRY_REVIEW_ONLY")
    assert result["buyerco.com"]["source_state"] == "CURRENT_THREAD_PENDING_VERIFIED_BUYBOX"
    source["partner_pilot_readiness_queue"][0]["activation_gates"] = {
        "buyer_buybox_received_and_verified": True,
        "current_target_geography_verified": True}
    unmatched=match_partner_buyboxes(source, allowed_domains={"buyerco.com"},
                                      source_state="CURRENT_REGISTRY_REVIEW_ONLY")
    assert unmatched["buyerco.com"]["geography_state"] == "GEO_GATE_REPORTED_SCOPE_NOT_INDEPENDENTLY_MATCHED"
    assert unmatched["buyerco.com"]["geography_independently_verified"] is False


def test_thread_or_duplicate_identity_cannot_spoof_partner_buybox():
    source=record(True)
    source["partner_pilot_readiness_queue"][0]["reviewed_gmail_thread_id"]="bad123"
    assert match_partner_buyboxes(source,allowed_domains={"buyerco.com"},
                                  source_state="CURRENT_REGISTRY_REVIEW_ONLY")=={}
    source=record(True)
    source["relationships"].append({
        "entity_key":"other","identity_domains":["buyerco.com"]})
    assert match_partner_buyboxes(source,allowed_domains={"buyerco.com"},
                                  source_state="CURRENT_REGISTRY_REVIEW_ONLY")=={}
    source=record(True)
    source["partner_pilot_readiness_queue"][0]["live_traffic_authorized"]=True
    assert match_partner_buyboxes(source,allowed_domains={"buyerco.com"},
                                  source_state="CURRENT_REGISTRY_REVIEW_ONLY")=={}


def test_owner_registry_requires_schema_permissions_and_freshness(tmp_path):
    p=tmp_path/"runtime/buyer_network_intelligence/commercial_relationship_registry_latest.json"
    p.parent.mkdir(parents=True)
    data=record()
    p.write_text(json.dumps(data))
    got, state=load_registry(tmp_path,now=NOW)
    assert got["schema_version"] == data["schema_version"]
    assert state == "PARTIAL_GMAIL_SNAPSHOT_REVIEW_ONLY"
    got, state=load_registry(tmp_path,now=NOW+timedelta(hours=4))
    assert got == {}
    data["outbound_sent"]=True
    p.write_text(json.dumps(data))
    got, state=load_registry(tmp_path,now=NOW)
    assert got == {}
