"""Buyer partner buybox reply tracking: original owner, no new sender."""
from datetime import datetime, timedelta, timezone
import json
import os

from empire_os.buyer_partner_buybox_reply_tracker import (
    read_original_gmail_metadata, review_partner_replies,
)
from test_buyer_qualification_evidence_bridge import record

NOW = datetime(2026, 10, 26, 20, 19, tzinfo=timezone.utc)
THREAD = "1a0cfb65e0dd960e"
INBOUND = "1a130e75c944ac00"


def sources():
    original = record()
    rel = original["relationships"][0]
    rel["last_inbound_message_id"] = INBOUND
    rel["last_inbound_at"] = "2026-10-12T16:17:01+00:00"
    rel["stage"] = "AWAITING_BUYER"
    rel["bounced_addresses"] = []
    pilot = original["partner_pilot_readiness_queue"][0]
    pilot["technical_review_packet"] = {
        "reported_inbound_requirements": {
            "evidence_grade": "HISTORICAL_REPORTED_UNVERIFIED",
            "source_ref": "gmail:" + INBOUND,
            "fields": {"agreement_or_form_details": "Form requested; not signed"},
            "commercial_terms_confirmed": False,
            "agreement_received_or_signed_verified": False,
            "founder_activation_authorized": False,
        }
    }
    gm = {
        "schema_version": "empire.buyer_mail_relationship_summary.v1",
        "origin": "connected_gmail_connector_read_only",
        "captured_at": "2026-10-09T20:47:26+00:00",
        "partial_update_at": NOW.isoformat(),
        "partial_updated_thread_ids": [THREAD],
        "threads": [{
            "gmail_thread_id": THREAD, "entity_key": "existing-partner",
            "identity_domains": ["buyerco.com"],
            "last_inbound_message_id": INBOUND,
        }],
        "connected_gmail_bridge": {
            "read_only": True, "outbound_authorized": False,
            "execution_authority": "NONE",
            "schema_version": "empire.connected_gmail_metadata_bridge.v1",
            "collected_at": NOW.isoformat(),
        }
    }
    matched = {"buyerco.com": {"entity_key": "existing-partner"}}
    return original, gm, matched


def test_baseline_then_no_duplicate_repeat_and_exact_partner_scope():
    raw, gmail, joined = sources()
    report, ids = review_partner_replies(
        raw, gmail, cohort_matches=joined, prior_message_ids=None,
        gmail_source_state="PARTIAL_METADATA_REFRESH_ORIGINAL_THREAD_CAPTURE_OLD")
    assert report["exact_entity_thread_identities"] == 1
    assert report["linked_to_original_research_cohort"] == 1
    assert report["changed_inbound_message_ids_review_only"] == 0
    assert report["repeat_full_request_already_blocked"] == 1
    row = report["partners"][0]
    assert row["reply_transition"] == "BASELINED_PREEXISTING_INBOUND_NOT_NEW"
    assert row["reported_fields_reviewed_not_accepted"] == ["agreement_or_form_details"]
    assert row["reported_fields_status"] == "HISTORICAL_REPORTED_UNVERIFIED"
    assert all(row[k] is False for k in (
        "accepted_geo_verified", "call_lead_criteria_verified",
        "operating_hours_caps_verified", "payable_terms_verified",
        "pilot_qualified", "automated_followup_authorized"))
    again, next_ids = review_partner_replies(
        raw, gmail, cohort_matches=joined, prior_message_ids=ids,
        gmail_source_state="PARTIAL_METADATA_REFRESH_ORIGINAL_THREAD_CAPTURE_OLD")
    assert again["partners"][0]["reply_transition"] == "MATCHED_INBOUND_MESSAGE_UNCHANGED"
    assert next_ids == ids


def test_real_message_id_change_needs_both_original_sources_then_review():
    raw, gmail, linked = sources()
    _, ids = review_partner_replies(raw, gmail, cohort_matches=linked,
                                   prior_message_ids=None,
                                   gmail_source_state="PARTIAL_METADATA_REFRESH_ORIGINAL_THREAD_CAPTURE_OLD")
    changed = "1a1311aa4444bb22"
    raw["relationships"][0]["last_inbound_message_id"] = changed
    missing, still = review_partner_replies(raw, gmail, cohort_matches=linked,
                                             prior_message_ids=ids,
                                             gmail_source_state="PARTIAL_METADATA_REFRESH_ORIGINAL_THREAD_CAPTURE_OLD")
    assert missing["changed_inbound_message_ids_review_only"] == 0
    assert still == ids
    gmail["threads"][0]["last_inbound_message_id"] = changed
    reported, updated = review_partner_replies(raw, gmail, cohort_matches=linked,
                                                prior_message_ids=ids,
                                                gmail_source_state="PARTIAL_METADATA_REFRESH_ORIGINAL_THREAD_CAPTURE_OLD")
    assert reported["changed_inbound_message_ids_review_only"] == 1
    row = reported["partners"][0]
    assert row["reply_transition"] == "CHANGED_INBOUND_MESSAGE_ID_REVIEW_REQUIRED"
    assert row["next_existing_owner_task"] == "REVIEW_NEW_INBOUND_METADATA_IN_ORIGINAL_GMAIL_THREAD"
    assert row["reported_fields_reviewed_not_accepted"] == []
    assert row["accepted_geo_verified"] is False
    assert updated["existing-partner"] == changed


def test_outside_research_cohort_stays_original_partner_and_suppression_hold():
    raw, gmail, _ = sources()
    raw["relationships"][0]["bounced_addresses"] = ["held@buyerco.com"]
    report, _ = review_partner_replies(raw, gmail, cohort_matches={},
                                      prior_message_ids=None,
                                      gmail_source_state="PARTIAL_METADATA_REFRESH_ORIGINAL_THREAD_CAPTURE_OLD")
    x = report["partners"][0]
    assert x["identity_status"] == "ORIGINAL_ENTITY_THREAD_MATCHED_OUTSIDE_RESEARCH_COHORT"
    assert x["suppression_or_delivery_hold"] is True
    assert x["next_existing_owner_task"] == "ORIGINAL_CONTACT_SUPPRESSION_OR_DELIVERY_REVIEW"
    assert x["automated_followup_authorized"] is False


def test_wrong_thread_or_unsafe_source_never_yields_new_reply():
    raw, gmail, joined = sources()
    gmail["threads"][0]["entity_key"] = "unrelated"
    report, seen = review_partner_replies(
        raw, gmail, cohort_matches=joined, prior_message_ids=None,
        gmail_source_state="PARTIAL_METADATA_REFRESH_ORIGINAL_THREAD_CAPTURE_OLD")
    assert report["partners"][0]["reply_transition"] == "INBOUND_NOT_CONFIRMED_BY_FRESH_GMAIL_METADATA"
    assert seen == {}
    raw, gmail, joined = sources()
    gm, seen = review_partner_replies(raw, {}, cohort_matches=joined,
                                      prior_message_ids={"existing-partner": INBOUND},
                                      gmail_source_state="GMAIL_METADATA_MISSING_UNSAFE_OR_STALE")
    assert gm["changed_inbound_message_ids_review_only"] == 0
    assert seen["existing-partner"] == INBOUND


def test_readonly_source_requires_current_partial_metadata_and_private_permissions(tmp_path):
    _, gm, _ = sources()
    path = tmp_path/"runtime/buyer_network_intelligence/gmail_relationship_evidence_latest.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(gm))
    os.chmod(path, 0o600)
    got, state = read_original_gmail_metadata(tmp_path, now=NOW)
    assert got["schema_version"] == gm["schema_version"]
    assert state == "PARTIAL_METADATA_REFRESH_ORIGINAL_THREAD_CAPTURE_OLD"
    got, state = read_original_gmail_metadata(tmp_path, now=NOW+timedelta(hours=4))
    assert got == {}
    os.chmod(path, 0o644)
    got, state = read_original_gmail_metadata(tmp_path, now=NOW)
    assert got == {}
