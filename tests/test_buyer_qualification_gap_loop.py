from datetime import datetime, timedelta, timezone
import json
import pytest

from empire_os.buyer_qualification_gap_loop import (
    evaluate, refresh_gap_loop, SCHEMA, GapAction,
)

NOW = datetime(2026, 10, 26, 19, 12, tzinfo=timezone.utc)


def item(domain: str, contact: str = "DISCOVERED_NO_CONFIRMED_CONTACT", *,
         fit=True, hold=False, current=True, inbound=None):
    return {
        "domain": domain, "tier": "FOUNDER_REVIEW_ONLY",
        "contact_history_state": contact,
        "contact_history_next_action": "REVIEW_ORIGINAL_THREAD",
        "contact_history_last_inbound_at": inbound,
        "active_demand_sector_research_fit": {
            "state": "FIRST_PARTY_SECTOR_RESEARCH_FIT" if fit
                     else "NO_SECTOR_GAP_MATCH_OBSERVED",
            "first_party_matching_sector_names": ["roofing"] if fit else [],
            "sample_corridors_for_research": [
                "corridor:v1:roofing:dallas_fort_worth:qualified_lead:lead"
            ] if fit else [],
            "market_or_zip_coverage_verified": False,
            "buyer_acceptance_verified": False,
        },
        "first_party_due_diligence": {
            "freshness": "CURRENT" if current else "STALE",
            "state": "NEEDS_FOUNDER_REVIEW", "observed_at": NOW.isoformat(),
        },
        "site_corroborated_buyer_role": True,
        "missing_evidence": ["verify_buyer_geography"] if fit else [],
        "manual_hold_reason": "DO_NOT_PURSUE" if hold else None,
        "automated_hold_reason": None,
        "outbound_authorized": False,
    }


def snapshot(rows):
    return {
        "schema_version": "empire.buyer_qualification_actions.v1",
        "mode": "OBSERVE", "execution_authority": "none",
        "outbound_sent": False, "outbound_enabled": False,
        "generated_at": NOW.isoformat(),
        "shortlisted_count": len(rows),
        "active_demand_source_state": "CURRENT_RESEARCH_PRIORITIES",
        "targets": rows,
    }


def test_relationship_and_sector_fit_routing_without_acceptance_claim():
    rows = [item("warmbuyer.com", "WORKSPACE_RECIPROCAL_THREAD_OBSERVED"),
            item("priorbuyer.com", "ALREADY_CONTACTED"),
            item("sectorbuyer.com"),
            item("holdbuyer.com", hold=True),
            item("unmatched.com", fit=False)]
    report, _ = evaluate(snapshot(rows), None, now=NOW)
    by = {x["domain"]: x for x in report["portfolio"]}
    assert report["companies_evaluated"] == 5
    assert report["first_party_sector_matches"] == 4
    assert report["live_relationships_with_first_party_match"] == 1
    assert report["prior_contacts_with_first_party_match"] == 1
    assert report["open_geo_verification"] == 4
    assert by["warmbuyer.com"]["action"] == GapAction.REVIEW_CONVERSATION_REQUIREMENTS.value
    assert by["priorbuyer.com"]["state"] == "WAITING_EXTERNAL_EVIDENCE"
    assert by["priorbuyer.com"]["new_intro_authorized"] is False
    assert by["sectorbuyer.com"]["action"] == GapAction.VERIFY_ACCEPTED_GEO_AND_INVENTORY.value
    assert by["holdbuyer.com"]["state"] == "POLICY_HELD"
    assert by["holdbuyer.com"]["owner"] is None
    assert "buyer_accepted_states_or_zips" in by["warmbuyer.com"]["missing_requirements"]
    assert all(x["buyer_accepted_geo_verified"] is False for x in by.values())
    assert all(x["buyer_commercial_acceptance_verified"] is False for x in by.values())
    assert report["outbound_authorized"] is False
    assert report["database_writes"] is False


def test_unchanged_snapshot_does_not_repeat_and_bounded_queue_progresses():
    rows = [item(f"company{i:03}.com") for i in range(47)]
    source = snapshot(rows)
    first, state = evaluate(source, None, now=NOW)
    assert len(first["newly_surfaced_reviews"]) == 20
    assert first["not_yet_surfaced_changed_reviews"] == 27
    for n, expected in [(1, 20), (2, 7), (3, 0)]:
        report, state = evaluate(source, state, now=NOW+timedelta(minutes=n*5))
        assert len(report["newly_surfaced_reviews"]) == expected
    assert report["duplicate_work_suppressed"] == 47
    assert len(report["portfolio"]) == 47


def test_new_buyer_inbound_reopens_review_and_site_timestamp_does_not():
    row = item("buyer.com", "WORKSPACE_RECIPROCAL_THREAD_OBSERVED",
               inbound="2026-10-26T09:00:00+00:00")
    source = snapshot([row])
    _, state = evaluate(source, None, now=NOW)
    row["first_party_due_diligence"]["observed_at"] = NOW.isoformat()
    unchanged, state = evaluate(source, state, now=NOW+timedelta(minutes=5))
    assert unchanged["newly_surfaced_reviews"] == []
    row["contact_history_last_inbound_at"] = "2026-10-26T19:10:00+00:00"
    changed, state = evaluate(source, state, now=NOW+timedelta(minutes=10))
    assert len(changed["newly_surfaced_reviews"]) == 1
    assert changed["newly_surfaced_reviews"][0]["owner"] == "existing_founder_commercial_review"


def test_source_stale_suppresses_sector_match_and_invalid_or_duplicate_fail_closed():
    source = snapshot([item("buyer.com")])
    source["active_demand_source_state"] = "UNAVAILABLE"
    report, _ = evaluate(source, None, now=NOW)
    assert report["first_party_sector_matches"] == 0
    assert report["open_geo_verification"] == 0
    source["generated_at"] = (NOW-timedelta(hours=6)).isoformat()
    with pytest.raises(ValueError):
        evaluate(source, None, now=NOW)
    duplicated = snapshot([item("buyer.com"),item("buyer.com")])
    with pytest.raises(ValueError):
        evaluate(duplicated, None, now=NOW)


def test_snapshot_io_and_stateful_cycle_no_additional_owner(tmp_path):
    root = tmp_path / "runtime/buyer_network_intelligence"
    root.mkdir(parents=True)
    (root/"founder_qualification_actions_latest.json").write_text(
        json.dumps(snapshot([item("buyer.com"), item("anotherbuyer.com")])))
    result = refresh_gap_loop(tmp_path, now=NOW)
    assert result["status"] == "ORIGINAL_BUYER_QUALIFICATION_GAP_LOOP_EVALUATED"
    report = json.loads((root/"qualification_gap_loop_latest.json").read_text())
    assert report["schema_version"] == SCHEMA
    assert result["new_reviews"] == 2
    next_result = refresh_gap_loop(tmp_path, now=NOW+timedelta(minutes=5))
    assert next_result["new_reviews"] == 0
    assert next_result["unchanged_suppressed"] == 2
    assert report["automatic_worker_dispatch"] is False
    assert report["revenue_verified"] is False


def test_recovered_real_reply_reopens_prior_contact_without_automated_send():
    prior = item("buyerreply.com", "ALREADY_CONTACTED")
    prior["contact_history_last_outbound_at"] = "2026-10-25T16:00:00+00:00"
    source = snapshot([prior])
    initial, memory = evaluate(source, None, now=NOW)
    assert initial["newly_surfaced_reviews"] == []
    assert initial["portfolio"][0]["state"] == "WAITING_EXTERNAL_EVIDENCE"
    prior["contact_history_last_inbound_at"] = "2026-10-26T18:30:00+00:00"
    reply, memory = evaluate(source, memory, now=NOW + timedelta(minutes=5))
    assert reply["newly_surfaced_reviews"][0]["action"] == GapAction.REVIEW_REPLY_AND_BUYER_CRITERIA.value
    assert reply["newly_surfaced_reviews"][0]["owner"] == "existing_buyer_gmail_evidence_owner"
    assert reply["newly_surfaced_reviews"][0]["new_intro_authorized"] is False
    same, memory = evaluate(source, memory, now=NOW+timedelta(minutes=10))
    assert same["newly_surfaced_reviews"] == []


def test_original_partner_buybox_links_only_exact_company_and_does_not_approve_geo():
    row=item("buyerco.com", "EXISTING_CONVERSATION")
    src=snapshot([row])
    contextual={
        "buyerco.com": {
            "entity_key": "existing-partner",
            "source": "original_commercial_relationship_registry",
            "source_state": "HISTORICAL_THREAD_CONTEXT_SOURCE_REFRESH_REQUIRED",
            "requirements_requested_not_verified": [
                "active_roofing_zips_and_buyer_markets",
                "accepted_jobs_and_qualified_billable_event"],
            "full_request_already_known": True,
            "geography_state": "NO_CURRENT_VERIFIED_BUYER_GEO_SCOPE",
            "geography_independently_verified": False,
            "buyer_pilot_qualified": False,
        },
    }
    initial, checkpoint=evaluate(src,None,now=NOW,buyer_partner_context=contextual,
                                  partner_source_state="PARTIAL_GMAIL_SNAPSHOT_REVIEW_ONLY")
    target=initial["portfolio"][0]
    assert initial["linked_partner_requirement_records"] == 1
    assert initial["previous_partner_buybox_requests_known"] == 1
    assert initial["independently_verified_buyer_coverage"] == 0
    assert initial["pilot_qualification_verified"] == 0
    assert "active_roofing_zips_and_buyer_markets" in target["missing_requirements"]
    assert target["buyer_accepted_geo_verified"] is False
    assert target["founder_outbound_buyer_requirements_repeat_blocked"] is True
    assert target["new_intro_authorized"] is False
    replay,checkpoint=evaluate(src,checkpoint,now=NOW+timedelta(minutes=5),
                               buyer_partner_context=contextual,
                               partner_source_state="PARTIAL_GMAIL_SNAPSHOT_REVIEW_ONLY")
    assert replay["newly_surfaced_reviews"]==[]
    assert replay["duplicate_work_suppressed"]==1


def test_actual_owner_gap_cycle_counts_unlinked_private_partner_buyboxes(tmp_path):
    base=tmp_path/"runtime/buyer_network_intelligence"
    base.mkdir(parents=True)
    (base/"founder_qualification_actions_latest.json").write_text(
        json.dumps(snapshot([item("existingpartner.com")])))
    registry={
        "schema_version":"empire.commercial_relationship_registry.v1",
        "generated_at":NOW.isoformat(),"mode":"OBSERVE",
        "execution_authority":"NONE","outbound_authorized":False,"outbound_sent":False,
        "next_actions_automatic_sends":False,"founder_actions_are_draft_only":True,
        "partner_pilot_readiness_is_activation_authority":False,
        "gmail_snapshot_fresh":False,
        "relationships":[{"entity_key":"one","identity_domains":["existingpartner.com"],
                          "gmail_thread_ids":["1a0cfb65e0dd960e"],"outbound_authorized":False,
                          "commercial_buyer_approved":False,"do_not_pursue":False}],
        "partner_pilot_readiness_queue":[
            {"entity_key":"one","reviewed_gmail_thread_id":"1a0cfb65e0dd960e",
             "activation_gates":{"buyer_buybox_received_and_verified":False},
             "single_pass_buyer_intake":{"execution_authority":"NONE","outbound_authorized":False,
                                         "repeat_full_request_blocked":True},
             "outbound_authorized":False,"live_traffic_authorized":False,
             "execution_authority":"NONE"},
            {"entity_key":"other","reviewed_gmail_thread_id":"1a0cfb65e0dd960f"},
        ],
    }
    (base/"commercial_relationship_registry_latest.json").write_text(json.dumps(registry))
    result=refresh_gap_loop(tmp_path,now=NOW)
    record=json.loads((base/"qualification_gap_loop_latest.json").read_text())
    assert result["linked_original_buyboxes"] == 1
    assert result["unlinked_partner_buyboxes"] == 1
    assert record["original_partner_buyboxes_in_source"] == 2
    assert record["partner_buyboxes_not_linked_to_candidate_cohort"] == 1
    assert record["unlinked_buyboxes_automatically_admitted"] == 0
    assert record["capacity_claims_accepted"] == 0


def test_original_gap_owner_baselines_existing_partner_reply_metadata_once(tmp_path):
    from test_buyer_qualification_evidence_bridge import record as registry_fixture
    from test_buyer_partner_buybox_reply_tracker import sources, NOW as INSTANT
    from os import chmod
    from pathlib import Path
    base=tmp_path/"runtime/buyer_network_intelligence"
    base.mkdir(parents=True)
    # Only original qualification can supply a research identity; the partner
    # reply tracker is allowed to retain entities outside this portfolio.
    src=snapshot([item("buyerco.com")])
    src["generated_at"]=INSTANT.isoformat()
    (base/"founder_qualification_actions_latest.json").write_text(json.dumps(src))
    registry, gmail, linked=sources()
    registry["generated_at"]=INSTANT.isoformat()
    (base/"commercial_relationship_registry_latest.json").write_text(json.dumps(registry))
    (base/"gmail_relationship_evidence_latest.json").write_text(json.dumps(gmail))
    chmod(base/"gmail_relationship_evidence_latest.json",0o600)
    first=refresh_gap_loop(tmp_path,now=INSTANT)
    assert first["partner_reply_changes_to_review"]==0
    out=json.loads((base/"qualification_gap_loop_latest.json").read_text())
    assert out["original_partner_buybox_reply_tracking"]["exact_entity_thread_identities"]==1
    assert out["original_partner_buybox_reply_tracking"]["partners"][0]["reply_transition"]=="BASELINED_PREEXISTING_INBOUND_NOT_NEW"
    second=refresh_gap_loop(tmp_path,now=INSTANT+timedelta(minutes=5))
    assert second["partner_reply_changes_to_review"]==0
    out=json.loads((base/"qualification_gap_loop_latest.json").read_text())
    assert out["original_partner_buybox_reply_tracking"]["partners"][0]["reply_transition"]=="MATCHED_INBOUND_MESSAGE_UNCHANGED"
    assert out["outbound_authorized"] is False
