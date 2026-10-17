import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from empire_os.commercial_relationship_registry import (
    RelationshipEvidenceError,
    reconcile,
)
from scripts.reconcile_buyer_email_relationships import (
    atomic_private_write,
    build,
)

NOW = datetime(2026, 10, 9, 20, 45, tzinfo=timezone.utc)


def row(key, domain, tid, inbound=None, outbound=None, bounce=None, company=None):
    return {
        "entity_key": key, "company": company or key,
        "identity_domains": [domain],
        "gmail_thread_id": tid,
        "last_inbound_at": inbound,
        "last_inbound_message_id": "abcdef1234567890" if inbound else None,
        "last_outbound_at": outbound,
        "last_outbound_message_id": "bcdefa1234567890" if outbound else None,
        "bounced_addresses": bounce or [],
        "next_action_code": "REQUEST_CURRENT_BUYBOX",
    }


def sources():
    source = {
        "schema_version": "empire.buyer_mail_relationship_summary.v1",
        "origin": "connected_gmail_connector_read_only",
        "mailbox": "flavag83@gmail.com",
        "captured_at": NOW.isoformat(),
        "threads": [
            row("lead-smart", "leadsmartinc.com", "1111111111111111",
                inbound="2026-10-09T19:30:00Z",
                outbound="2026-10-09T19:00:00Z"),
            row("validated", "homeservicesleadgroup.com", "2222222222222222",
                outbound="2026-10-07T19:00:00Z",
                bounce=["info@homeservicesleadgroup.com"]),
            row("validated", "validatedlg.ai", "3333333333333333",
                inbound="2026-10-07T09:00:00Z",
                outbound="2026-10-07T20:00:00Z"),
            row("bad-recipient", "positioncalls.com", "4444444444444444",
                outbound="2026-09-26T12:00:00Z",
                bounce=["affiliates@positioncalls.com"]),
            row("no-reply", "newbuyer.com", "5555555555555555",
                outbound="2026-09-25T12:00:00Z"),
        ],
    }
    queue = {
        "candidate_count": 3,
        "generated_at": NOW.isoformat(),
        "candidates": [
            {"domain": "validatedlg.ai", "status": "VERIFY_REQUIREMENTS"},
            {"domain": "positioncalls.com", "status": "WATCH"},
            {"domain": "onlydiscovered.com", "status": "WATCH"},
        ],
    }
    qualification = {
        "shortlisted_count": 1,
        "targets": [{"domain": "positioncalls.com", "tier": "EVIDENCE_RECOVERY",
                     "founder_priority": 90}],
    }
    return source, queue, qualification


def test_one_relationship_per_company_and_multiple_threads():
    src, queue, qual = sources()
    d = reconcile(src, queue, qual, now=NOW)
    records = {x["entity_key"]: x for x in d["relationships"]}
    assert len(records) == 5
    assert d["linked_gmail_thread_count"] == 5
    assert len(records["validated"]["gmail_thread_ids"]) == 2
    assert records["validated"]["stage"] == "AWAITING_BUYER"
    assert records["validated"]["bounced_addresses"] == [
        "info@homeservicesleadgroup.com"
    ]
    assert records["lead-smart"]["stage"] == "INBOUND_REVIEW_REQUIRED"
    assert records["bad-recipient"]["stage"] == "DELIVERY_HOLD"
    assert records["no-reply"]["stage"] == "CONTACTED_AWAITING_RESPONSE"
    assert records["onlydiscovered.com"]["stage"] == "RESEARCH_ONLY"
    assert records["bad-recipient"]["founder_priority"] == 90
    assert all(x["outbound_authorized"] is False for x in d["relationships"])
    assert all(x["commercial_buyer_approved"] is False for x in d["relationships"])


def test_gmail_snapshot_staleness_does_not_claim_current_mailbox():
    src, queue, qual = sources()
    future = NOW + timedelta(days=8)
    d = reconcile(src, queue, qual, now=future)
    assert d["gmail_snapshot_fresh"] is False
    assert d["automatic_live_gmail_ingest_configured"] is False
    assert not any(x["gmail_snapshot_fresh"] for x in d["relationships"])
    assert d["outbound_authorized"] is False


def test_new_inbound_only_on_changed_id_between_snapshots():
    src, queue, qual = sources()
    old = reconcile(src, queue, qual, now=NOW)
    again = reconcile(src, queue, qual, now=NOW, previous=old)
    assert again["new_inbound_relationships_since_prior_snapshot"] == 0
    updated = copy.deepcopy(src)
    updated["threads"][0]["last_inbound_message_id"] = "fabcdef123456789"
    updated["threads"][0]["last_inbound_at"] = "2026-10-09T19:45:00Z"
    newer = reconcile(updated, queue, qual, now=NOW, previous=old)
    assert newer["new_inbound_relationships_since_prior_snapshot"] == 1


def test_manual_hold_overrides_buyer_reply():
    src, queue, qual = sources()
    qual["targets"] = [{"domain":"leadsmartinc.com","tier":"MANUAL_EVIDENCE_HOLD","founder_priority":99}]
    d = reconcile(src, queue, qual, now=NOW)
    record = next(x for x in d["relationships"] if x["entity_key"]=="lead-smart")
    assert record["stage"] == "EVIDENCE_HOLD"
    assert record["outbound_authorized"] is False


@pytest.mark.parametrize("mutation", [
    lambda s: s.update(mailbox="private-other-account@example.com"),
    lambda s: s.update(origin="untrusted_user_file"),
    lambda s: s["threads"][0].update(gmail_thread_id="../../etc/passwd"),
    lambda s: s["threads"][0].update(next_action_code="SEND_NOW"),
    lambda s: s["threads"][0].update(last_inbound_at="2026-10-09T23:59:00Z"),
    lambda s: s["threads"][0].update(last_inbound_at="not a date"),
])
def test_untrusted_sources_cannot_grant_commercial_action(mutation):
    src, queue, qual = sources()
    mutation(src)
    with pytest.raises(RelationshipEvidenceError):
        reconcile(src, queue, qual, now=NOW)


def test_reject_ambiguous_alias_claims():
    src, queue, qual = sources()
    src["threads"].append(row("other", "validatedlg.ai", "6666666666666666",
                              outbound="2026-10-08T19:00:00Z"))
    with pytest.raises(RelationshipEvidenceError, match="ambiguous_company_alias"):
        reconcile(src, queue, qual, now=NOW)


def test_refuse_inconsistent_canonical_snapshot_counts():
    src, queue, qual = sources()
    queue["candidate_count"] += 1
    with pytest.raises(RelationshipEvidenceError):
        reconcile(src, queue, qual, now=NOW)


def test_private_atomic_output_and_repeatable_cli_read(tmp_path):
    root = tmp_path
    directory = root / "runtime/buyer_network_intelligence"
    directory.mkdir(parents=True)
    src, queue, qual = sources()
    for n, d in (
        ("gmail_relationship_evidence_latest.json",src),
        ("candidate_queue_latest.json", queue),
        ("founder_qualification_actions_latest.json",qual),
    ):
        (directory/n).write_text(json.dumps(d))
    # Current wall-clock is not used for fixture capture; exercise pure reconcile
    # explicitly at NOW and atomic output separately.
    report = reconcile(src, queue, qual, now=NOW)
    file = directory/"commercial_relationship_registry_latest.json"
    atomic_private_write(file,report)
    assert file.stat().st_mode & 0o777 == 0o600
    assert json.loads(file.read_text())["relationship_count"]==5
    atomic_private_write(file,report)
    assert json.loads(file.read_text())["outbound_sent"] is False


def test_no_raw_message_body_or_email_send_keys():
    d = reconcile(*sources(),now=NOW)
    s = json.dumps(d).lower()
    for forbidden in ('"body":','"message_body":','"password":',
                      '"smtp_password":','"execution_authority": "send"'):
        assert forbidden not in s


def test_founder_action_classifies_inbound_without_sending_or_fake_approval():
    src,queue,qual=sources()
    src['threads'][0]['next_action_code']='LANDING_APPROVAL_AND_ROUTE_PROOF'
    report=reconcile(src,queue,qual,now=NOW)
    row=next(x for x in report['relationships'] if x['entity_key']=='lead-smart')
    assert row['stage']=='INBOUND_REVIEW_REQUIRED'
    assert row['next_founder_action']=='REVIEW_BUYER_LANDING_APPROVAL_AND_ROUTE'
    assert row['founder_review_required'] is True
    assert row['auto_send_authorized'] is False
    assert report['founder_action_queue'][0]['entity_key']=='lead-smart'
    assert report['founder_action_queue'][0]['outbound_authorized'] is False
    assert report['next_actions_automatic_sends'] is False
    assert report['founder_actions_are_draft_only'] is True


def test_partner_waiting_no_repeat_auto_followup_and_overdue_is_review_only():
    src,queue,qual=sources()
    first=reconcile(src,queue,qual,now=NOW)
    pending=next(x for x in first['relationships'] if x['entity_key']=='validated')
    assert pending['next_founder_action']=='WAIT_BUYER_RESPONSE'
    assert pending['founder_review_required'] is False
    later=reconcile(src,queue,qual,now=NOW+timedelta(days=8))
    later_item=next(x for x in later['relationships'] if x['entity_key']=='validated')
    # Once the Gmail snapshot is stale, source freshness takes precedence
    # over a potentially outdated last-sent timestamp.
    assert later['gmail_snapshot_fresh'] is False
    assert later_item['next_founder_action']=='REFRESH_MAILBOX_EVIDENCE'
    assert later_item['auto_send_authorized'] is False


def test_seven_day_review_due_not_automatic_email():
    src,queue,qual=sources()
    # Refresh the imported snapshot timestamp so old emails remain current
    # evidence for this focused test of the review threshold.
    now=NOW+timedelta(days=8)
    src['captured_at']=now.isoformat()
    result=reconcile(src,queue,qual,now=now)
    validated=next(x for x in result['relationships'] if x['entity_key']=='validated')
    assert validated['stage']=='AWAITING_BUYER'
    assert validated['next_founder_action']=='REVIEW_PENDING_BUYER_REQUEST'
    assert validated['founder_action_reason']=='FOLLOWUP_REVIEW_DUE'
    assert validated['founder_review_required'] is True
    assert validated['outbound_authorized'] is False
    assert result['outbound_sent'] is False


def test_registry_action_queue_respects_holds_and_deliverability():
    report=reconcile(*sources(),now=NOW)
    by_key={x['entity_key']:x for x in report['relationships']}
    assert by_key['bad-recipient']['next_founder_action']=='VERIFY_DELIVERY_CHANNEL_NO_RETRY'
    assert by_key['bad-recipient']['founder_review_required'] is True
    src,queue,qual=sources()
    qual['targets']=[{'domain':'leadsmartinc.com','tier':'AUTOMATED_EVIDENCE_HOLD','founder_priority':95}]
    held=reconcile(src,queue,qual,now=NOW)
    lead=next(x for x in held['relationships'] if x['entity_key']=='lead-smart')
    assert lead['next_founder_action']=='REVIEW_EVIDENCE_HOLD_NO_CONTACT'
    assert lead['outbound_authorized'] is False


def test_warm_relationships_always_visible_separately_from_cold_delivery_backlog():
    report=reconcile(*sources(),now=NOW)
    warm=report['warm_business_action_queue']
    assert report['warm_business_relationship_count']==2
    assert [x['entity_key'] for x in warm]==['lead-smart','validated']
    assert all(x['outbound_authorized'] is False for x in warm)
    assert all(x['partner_commercial_terms_verified'] is False for x in warm)
    assert all(x['gmail_snapshot_fresh'] is True for x in warm)
    assert all(x['entity_key']!='bad-recipient' for x in warm)
    assert report['warm_business_queue_truncated'] is False


def test_existing_registry_builder_reads_social_signal_evidence_without_contact_upgrade(tmp_path):
    from datetime import datetime, timezone

    root = tmp_path
    base = root / "runtime/buyer_network_intelligence"
    base.mkdir(parents=True)
    src, queue, qual = sources()
    src["captured_at"] = datetime.now(timezone.utc).isoformat()
    for name, data in (
        ("gmail_relationship_evidence_latest.json", src),
        ("candidate_queue_latest.json", queue),
        ("founder_qualification_actions_latest.json", qual),
    ):
        path = base / name
        path.write_text(json.dumps(data))
        if name.startswith("gmail_"):
            path.chmod(0o600)
    stamp = datetime.now(timezone.utc).isoformat()
    social = root / "runtime/acquisition/signal_inbox.json"
    social.parent.mkdir(parents=True)
    social.write_text(json.dumps({
        "s1": {
            "source": "reddit_intent",
            "status": "unresolved",
            "lead_score": 92,
            "url": "https://www.reddit.com/r/roofing/comments/123/needleads",
            "raw": {
                "community_intent": {
                    "observed_at": stamp,
                    "url": "https://www.reddit.com/r/roofing/comments/123/needleads",
                    "intent_score": 92,
                    "niche": "roofing",
                    "evidence_urls": ["https://roofingpros.com"],
                }
            },
        }
    }))
    community = root/"runtime/community_intent/latest.json"
    community.parent.mkdir(parents=True)
    community.write_text(json.dumps({
        "observed_at":stamp,
        "source_status":{
            "reddit":{"ok":True,"accepted_observations":1},
            "linkedin":{"ok":False,"accepted_observations":0},
        }
    }))
    linkedin = root/"runtime/buyer_acquisition/linkedin_revenue_department_latest.json"
    linkedin.parent.mkdir(parents=True)
    linkedin.write_text(json.dumps({
        "generated_at":stamp,
        "candidate_count":9,
        "human_review_ready_count":0,
        "verified_contact_count":0,
    }))
    result = build(root)
    assert result["relationship_count"]==5
    assert result["social_intent_review"]["sources"]["reddit_intent"]==1
    assert result["social_intent_review"]["evidence_bearing_recent_signal_count"]==1
    assert result["social_intent_review"]["verified_commercial_buying_intent_count"]==0
    assert result["outbound_authorized"] is False
    assert not any(x["outbound_authorized"] for x in result["relationships"])


def test_existing_founder_registry_displays_source_learning_without_buying_claim(
    tmp_path,
):
    from empire_os.community_intent_learning import record_episode, snapshot, write_snapshot

    src, queue, qual = sources()
    src["captured_at"] = datetime.now(timezone.utc).isoformat()
    base=tmp_path/"runtime/buyer_network_intelligence"
    base.mkdir(parents=True)
    for name, data in (
        ("gmail_relationship_evidence_latest.json",src),
        ("candidate_queue_latest.json",queue),
        ("founder_qualification_actions_latest.json",qual),
    ):
        path=base/name
        path.write_text(json.dumps(data))
        if name.startswith("gmail_"):
            path.chmod(0o600)
    research=("RoofingSales","marketing leads","roofing","US")
    date=datetime.now(timezone.utc)
    episodes,entry=record_episode([],source=research,slot=222,
        retrieval_ok=True,observations=[],previously_observed_urls=set(),
        now=date)
    proof=snapshot(episodes,[research],now=date,latest=entry,
                   next_source=research)
    learning=tmp_path/"runtime/community_intent/source_learning_latest.json"
    learning.parent.mkdir(parents=True)
    write_snapshot(learning,proof)
    enriched=build(tmp_path)
    record=enriched["icp_research_learning"]
    assert record["status"]=="OBSERVE"
    assert record["episode_count"]==1
    assert record["next_research_task"]=="RESEARCH_NEXT_ICP_SOURCE"
    assert record["verified_buyer_conversions"]==0
    assert record["recognized_revenue_cents"] is None
    assert enriched["outbound_authorized"] is False


def test_three_warm_partner_pilots_have_independent_fail_closed_gates():
    from empire_os.commercial_relationship_registry import (
        PARTNER_PILOT_SCOPES,
        PARTNER_LAUNCH_GATES,
    )
    src, queue, qual = sources()
    for key, domain in (
        ("leadbank","alliancevs.io"),
        ("validated","validatedlg.ai"),
        ("connexis","connex.is"),
    ):
        spec=PARTNER_PILOT_SCOPES[key]
        src["threads"].append(row(
            key, domain, spec["reviewed_thread"],
            inbound="2026-10-09T18:00:00Z",
            outbound="2026-10-09T19:00:00Z",
        ))
    result=reconcile(src,queue,qual,now=NOW)
    queue_out={x["entity_key"]: x for x in result["partner_pilot_readiness_queue"]}
    assert set(queue_out)=={"leadbank","validated","connexis"}
    assert result["partner_pilot_readiness_is_activation_authority"] is False
    for item in queue_out.values():
        assert item["two_way_gmail_thread_observed"] is True
        assert item["activation_stage"]=="WAITING_BUYER_BUYBOX"
        assert item["gate_count_verified"]==0
        assert item["gate_count_total"]==len(PARTNER_LAUNCH_GATES)
        assert set(item["activation_gates"])==set(PARTNER_LAUNCH_GATES)
        assert all(x is False for x in item["activation_gates"].values())
        assert item["isolated_buyer_route_required"] is True
        assert item["lead_smart_route_and_terms_reused"] is False
        assert item["contract_signing_authorized"] is False
        assert item["outbound_authorized"] is False
        assert item["live_traffic_authorized"] is False
        assert item["execution_authority"]=="NONE"


def test_pilot_cannot_be_promoted_when_gmail_snapshot_is_stale():
    from empire_os.commercial_relationship_registry import PARTNER_PILOT_SCOPES
    src, queue, qual = sources()
    src["threads"].append(row(
        "leadbank", "alliancevs.io",
        PARTNER_PILOT_SCOPES["leadbank"]["reviewed_thread"],
        inbound="2026-10-09T19:00:00Z",
        outbound="2026-10-09T19:10:00Z",
    ))
    report=reconcile(src,queue,qual,now=NOW+timedelta(days=5))
    target=next(x for x in report["partner_pilot_readiness_queue"]
                if x["entity_key"]=="leadbank")
    assert target["mailbox_snapshot_fresh"] is False
    assert target["activation_stage"]=="REVIEW_RELATIONSHIP_EVIDENCE"
    assert all(v is False for v in target["activation_gates"].values())


def test_pilot_does_not_inherit_verified_tracking_from_lead_smart():
    from empire_os.commercial_relationship_registry import PARTNER_PILOT_SCOPES
    src, queue, qual = sources()
    src["threads"].append(row(
        "validated", "validatedlg.ai",
        PARTNER_PILOT_SCOPES["validated"]["reviewed_thread"],
        inbound="2026-10-09T18:00:00Z",
        outbound="2026-10-09T19:00:00Z",
    ))
    report=reconcile(src,queue,qual,now=NOW)
    target=next(x for x in report["partner_pilot_readiness_queue"]
                if x["entity_key"]=="validated")
    assert target["activation_gates"]["partner_specific_tracking_verified"] is False
    assert target["activation_gates"]["partner_specific_routing_verified"] is False
    assert target["activation_gates"]["buyer_landing_approved"] is False
    assert target["gate_count_verified"] == 0


def test_leadbank_actual_reply_promises_documents_not_approvals():
    from empire_os.commercial_relationship_registry import (
        PARTNER_PILOT_SCOPES,
    )
    src, queue, qual = sources()
    partner=PARTNER_PILOT_SCOPES["leadbank"]
    observed=row(
        "leadbank", "alliancevs.io", partner["reviewed_thread"],
        inbound="2026-10-09T23:29:13Z",
        outbound="2026-10-09T23:25:27Z",
    )
    observed["last_inbound_message_id"]="1a1230003eb39320"
    observed["last_outbound_message_id"]="1a122fc6010e3b5b"
    src["threads"].append(observed)
    recent=datetime(2026,10,9,23,45,tzinfo=timezone.utc)
    report=reconcile(src,queue,qual,now=recent)
    state=next(x for x in report["partner_pilot_readiness_queue"]
               if x["entity_key"]=="leadbank")
    asset=state["technical_review_packet"]
    assert state["activation_stage"]=="ONBOARDING_DOCUMENTS_AND_TECH_HANDOFF_PROMISED"
    assert state["agreement_and_handoff_promised_not_received"] is True
    assert state["current_next_partner_task"]=="REVIEW_AGREEMENT_AND_MAHAD_SPEC_ON_RECEIPT"
    evidence=asset["buyer_commercial_source_evidence"]
    assert evidence["inbound_message_id"]=="1a1230003eb39320"
    assert evidence["agreement_and_onboarding_form_promised"] is True
    assert evidence["mahad_technical_questions_forwarded"] is True
    assert evidence["agreement_received"] is False
    assert evidence["commercial_buybox_received"] is False
    assert state["gate_count_verified"]==0
    assert all(v is False for v in state["activation_gates"].values())
    assert asset["partner_tracking_number"] is None
    assert asset["routing_provider_selected"] is None
    assert asset["partner_tracking_campaign_id"] is None
    assert asset["signed_agreement_evidence"] is None
    assert asset["traffic_enabled"] is False
    assert asset["lead_smart_route_or_number_inherited"] is False
    assert asset["actual_revenue"] is False


def test_newer_unread_inbound_cannot_inherit_old_leadbank_promise_as_current():
    from empire_os.commercial_relationship_registry import PARTNER_PILOT_SCOPES
    src,queue,qual=sources()
    record=row(
        "leadbank", "alliancevs.io",
        PARTNER_PILOT_SCOPES["leadbank"]["reviewed_thread"],
        inbound="2026-10-09T23:40:00Z",
        outbound="2026-10-09T23:25:27Z",
    )
    record["last_inbound_message_id"]="fedcba1234567890"
    src["threads"].append(record)
    report=reconcile(src,queue,qual,now=datetime(2026,10,9,23,50,tzinfo=timezone.utc))
    s=next(x for x in report["partner_pilot_readiness_queue"]
           if x["entity_key"]=="leadbank")
    assert s["agreement_and_handoff_promised_not_received"] is False
    assert s["technical_review_packet"]["buyer_commercial_source_evidence"] is None
    assert s["activation_stage"]=="WAITING_BUYER_BUYBOX"


def test_partner_technical_pilot_review_packets_are_buyer_isolated():
    from empire_os.commercial_relationship_registry import PARTNER_PILOT_SCOPES
    src,queue,qual=sources()
    for key,domain in (
        ("leadbank","alliancevs.io"),
        ("validated","validatedlg.ai"),
        ("connexis","connex.is")
    ):
        spec=PARTNER_PILOT_SCOPES[key]
        src["threads"].append(row(
            key,domain,spec["reviewed_thread"],
            inbound="2026-10-09T18:00:00Z",
            outbound="2026-10-09T19:00:00Z",
        ))
    report=reconcile(src,queue,qual,now=NOW)
    packets={r["entity_key"]:r["technical_review_packet"]
             for r in report["partner_pilot_readiness_queue"]}
    assert set(packets)=={"leadbank","validated","connexis"}
    namespaces={p["proposed_landing_review_asset"] for p in packets.values()}
    assert len(namespaces)==3
    for key,p in packets.items():
        assert p["entity_key"]==key
        assert p["proposed_landing_review_asset"].startswith("review-only://")
        assert p["company_site_source"]=="https://empire-ai.co.uk"
        for field in (
            "external_buyer_program_id","verified_target_zips_or_postcodes",
            "verified_buyer_hours_timezone","verified_payout_and_settlement",
            "verified_billable_event","partner_tracking_number",
            "partner_tracking_campaign_id","routing_destination_or_sip_endpoint",
        ):
            assert p[field] is None
        assert p["traffic_source_accepted_by_buyer"] is False
        assert p["buyer_commercial_terms_inherited"] is False
        assert p["contract_signing_authorized"] is False
        assert p["landing_page_created_or_published"] is False
        assert p["execution_authority"]=="NONE"


def test_public_partner_programmes_never_promote_commercial_launch_gates():
    from empire_os.commercial_relationship_registry import (
        PARTNER_PUBLIC_PROGRAMME_REFERENCES,
        PARTNER_PILOT_SCOPES,
    )
    src, queue, qualification = sources()
    for key, domain in (
        ("leadbank", "alliancevs.io"),
        ("validated", "validatedlg.ai"),
        ("connexis", "connex.is"),
    ):
        src["threads"].append(row(
            key, domain, PARTNER_PILOT_SCOPES[key]["reviewed_thread"],
            inbound="2026-10-09T18:00:00Z",
            outbound="2026-10-09T19:00:00Z",
        ))
    result = reconcile(src, queue, qualification, now=NOW)
    records = {x["entity_key"]: x
               for x in result["partner_pilot_readiness_queue"]}
    assert set(records) <= set(PARTNER_PUBLIC_PROGRAMME_REFERENCES)
    assert records["leadbank"]["technical_review_packet"]["official_public_programme_references"] == []
    assert len(records["validated"]["technical_review_packet"]["official_public_programme_references"]) == 2
    assert len(records["connexis"]["technical_review_packet"]["official_public_programme_references"]) == 2
    assert records["connexis"]["current_next_partner_task"] == "CLARIFY_CONNEXIS_LIVE_CALLS_VS_API_CPL_TERMS"
    assert records["validated"]["current_next_partner_task"] == "CONFIRM_VALIDATED_AFFILIATE_TERMS_AND_BUYBOX"
    for key, rec in records.items():
        info = rec["technical_review_packet"]
        assert info["selected_partner_offer_format"] is None
        assert info["general_public_programme_bound_to_this_account"] is False
        assert info["applicable_payout_model_confirmed_by_partner"] is False
        assert info["contract_signing_channel_confirmed"] is False
        assert info["web_or_portal_acceptance_authorized"] is False
        assert info["partner_tracking_number"] is None
        assert info["verified_payout_and_settlement"] is None
        assert info["traffic_enabled"] is False
        assert info["contract_signing_authorized"] is False
        assert rec["gate_count_verified"] == 0
        assert all(v is False for v in rec["activation_gates"].values())
        for source in info["official_public_programme_references"]:
            assert source["source"].startswith("https://")
            assert source["checked_date"] == "2026-10-10"
            assert source["not_corroborated"]
            assert source["next_question"]
    assert result["outbound_authorized"] is False


def test_public_connexis_api_and_paypercall_terms_cannot_be_collapsed():
    from empire_os.commercial_relationship_registry import PARTNER_PUBLIC_PROGRAMME_REFERENCES
    refs = PARTNER_PUBLIC_PROGRAMME_REFERENCES["connexis"]
    assert len(refs) == 2
    assert {x["reference_type"] for x in refs} == {
        "PUBLIC_PAY_PER_CALL_PROGRAMME",
        "PUBLIC_API_CPL_PUBLISHER_TERMS",
    }
    calls = next(x for x in refs if x["reference_type"] == "PUBLIC_PAY_PER_CALL_PROGRAMME")
    leads = next(x for x in refs if x["reference_type"] == "PUBLIC_API_CPL_PUBLISHER_TERMS")
    assert "without a minimum" in calls["public_observation"]
    assert "£50" in leads["public_observation"]
    assert "90%" in leads["public_observation"]
    assert calls["source"] != leads["source"]


def _prepared_leadbank_for_reported_terms():
    from empire_os.commercial_relationship_registry import PARTNER_PILOT_SCOPES
    src, queue, qual = sources()
    row2 = row(
        "leadbank", "alliancevs.io",
        PARTNER_PILOT_SCOPES["leadbank"]["reviewed_thread"],
        inbound="2026-10-09T20:30:00Z",
        outbound="2026-10-09T20:15:00Z",
    )
    row2["last_inbound_message_id"] = "1a1230003eb39320"
    src["threads"].append(row2)
    return reconcile(src,queue,qual,now=NOW)


def _reviewed_leadbank_claim():
    return {
        "schema_version":"empire.partner_inbound_requirements.v1",
        "origin":"connected_gmail_explicit_review",
        "observations":[{
            "entity_key":"leadbank",
            "gmail_thread_id":"1a0cfb65e0dd960e",
            "inbound_message_id":"1a1230003eb39320",
            "reviewed_at":"2026-10-09T20:40:00Z",
            "reported_fields":{
                "programme_format":"Pay-per-call, reported by partner",
                "buyer_market_coverage":"Texas ZIP subset reported",
                "tracking_and_routing_instructions":"Partner states direct call route",
                "agreement_or_form_details":"Agreement attachment reported by sender",
            },
        }],
    }


def test_genuine_gmail_bound_partner_reported_terms_are_triage_only():
    from empire_os.commercial_relationship_registry import attach_partner_inbound_requirements
    report=_prepared_leadbank_for_reported_terms()
    out=attach_partner_inbound_requirements(report,_reviewed_leadbank_claim())
    row2=next(x for x in out["partner_pilot_readiness_queue"]
              if x["entity_key"]=="leadbank")
    p=row2["technical_review_packet"]
    assert row2["inbound_requirement_review_status"]=="REPORTED_AWAITING_INDEPENDENT_VERIFICATION"
    assert row2["inbound_requirement_field_count"]==4
    assert row2["current_next_partner_task"]=="REVIEW_REPORTED_BUYBOX_AND_AGREEMENT_EVIDENCE"
    assert p["reported_inbound_requirements"]["source_ref"]=="gmail:1a1230003eb39320"
    assert p["reported_inbound_requirements"]["evidence_grade"]=="CURRENT_REPORTED_UNVERIFIED"
    assert p["reported_inbound_requirements"]["agreement_received_or_signed_verified"] is False
    assert p["verified_target_zips_or_postcodes"] is None
    assert p["verified_payout_and_settlement"] is None
    assert p["signed_agreement_evidence"] is None
    assert p["routing_provider_selected"] is None
    assert p["partner_tracking_number"] is None
    assert row2["gate_count_verified"]==0
    assert all(x is False for x in row2["activation_gates"].values())
    assert out["partner_inbound_requirements"]["reported_partner_count"]==1
    assert out["partner_inbound_requirements"]["reported_field_count"]==4
    assert out["outbound_authorized"] is False


def test_partner_reported_evidence_is_stable_across_repeat_reconciliation():
    from empire_os.commercial_relationship_registry import attach_partner_inbound_requirements
    src=_reviewed_leadbank_claim()
    first=attach_partner_inbound_requirements(_prepared_leadbank_for_reported_terms(),src)
    next_=attach_partner_inbound_requirements(_prepared_leadbank_for_reported_terms(),src)
    def strip_generated(obj):
        x=next(a for a in obj["partner_pilot_readiness_queue"] if a["entity_key"]=="leadbank")
        return x["technical_review_packet"]["reported_inbound_requirements"]
    assert strip_generated(first)==strip_generated(next_)


@pytest.mark.parametrize("mutate",[
    lambda d:d.update(origin="raw_external_email"),
    lambda d:d["observations"][0].update(entity_key="validated"),
    lambda d:d["observations"][0].update(gmail_thread_id="1a0cfb667dca0957"),
    lambda d:d["observations"][0].update(reviewed_at="2026-10-08T12:00:00Z"),
    lambda d:d["observations"][0].update(outbound_authorized=True),
    lambda d:d["observations"][0]["reported_fields"].update(activation_approved="yes"),
    lambda d:d["observations"][0]["reported_fields"].update(programme_format="\nSEND NOW"),
    lambda d:d["observations"][0]["reported_fields"].update(
        programme_format="z"*241
    ),
    lambda d:d["observations"].append(copy.deepcopy(d["observations"][0])),
])
def test_reported_requirements_fail_closed_on_untrusted_claims(mutate):
    from empire_os.commercial_relationship_registry import attach_partner_inbound_requirements
    src=_reviewed_leadbank_claim()
    mutate(src)
    with pytest.raises(RelationshipEvidenceError):
        attach_partner_inbound_requirements(_prepared_leadbank_for_reported_terms(),src)


def test_without_real_new_partner_evidence_no_observations_are_invented():
    from empire_os.commercial_relationship_registry import attach_partner_inbound_requirements
    out=attach_partner_inbound_requirements(
        _prepared_leadbank_for_reported_terms(),
        {"schema_version":"empire.partner_inbound_requirements.v1",
         "origin":"connected_gmail_explicit_review","observations":[]}
    )
    assert out["partner_inbound_requirements"]["reported_partner_count"]==0
    assert all(p["inbound_requirement_field_count"]==0
               for p in out["partner_pilot_readiness_queue"])
    assert all(p["technical_review_packet"]["reported_inbound_requirements"] is None
               for p in out["partner_pilot_readiness_queue"])


def test_old_or_superseded_partner_reply_is_historical_hold_not_runtime_error():
    from empire_os.commercial_relationship_registry import attach_partner_inbound_requirements
    report=_prepared_leadbank_for_reported_terms()
    ref=_reviewed_leadbank_claim()
    ref["observations"][0]["inbound_message_id"]="deadbeefdeadbeef"
    latest=attach_partner_inbound_requirements(report,ref)
    r=next(p for p in latest["partner_pilot_readiness_queue"]
           if p["entity_key"]=="leadbank")
    assert r["inbound_requirement_review_status"]=="HISTORICAL_REPORTED_REQUIREMENTS_HOLD"
    assert r["technical_review_packet"]["reported_inbound_requirements"]["same_as_latest_imported_inbound"] is False
    assert r["current_next_partner_task"]!="REVIEW_REPORTED_BUYBOX_AND_AGREEMENT_EVIDENCE"
    assert latest["partner_inbound_requirements"]["historical_hold_count"]==1
    assert latest["partner_inbound_requirements"]["current_review_count"]==0
    assert r["gate_count_verified"]==0
    assert r["live_traffic_authorized"] is False


def test_old_gmail_snapshot_does_not_block_safe_onboarding_monitor():
    from empire_os.commercial_relationship_registry import attach_partner_inbound_requirements
    state=_prepared_leadbank_for_reported_terms()
    relation=next(x for x in state["relationships"] if x["entity_key"]=="leadbank")
    relation["gmail_snapshot_fresh"]=False
    state=attach_partner_inbound_requirements(state,_reviewed_leadbank_claim())
    r=next(p for p in state["partner_pilot_readiness_queue"] if p["entity_key"]=="leadbank")
    assert r["inbound_requirement_review_status"]=="HISTORICAL_REPORTED_REQUIREMENTS_HOLD"
    assert r["gate_count_verified"]==0


def test_reported_requirement_ledger_file_is_private_and_optional(tmp_path):
    from scripts.reconcile_buyer_email_relationships import build
    root=tmp_path
    base=root/"runtime/buyer_network_intelligence"
    base.mkdir(parents=True)
    src,queue,qual=sources()
    for name,payload in (
        ("gmail_relationship_evidence_latest.json",src),
        ("candidate_queue_latest.json",queue),
        ("founder_qualification_actions_latest.json",qual),
    ):
        path=base/name
        path.write_text(json.dumps(payload))
        path.chmod(0o600)
    # This test requires no live Gmail, network, logging, contracts or routes.
    empty=build(root)
    assert empty["partner_inbound_requirements"]["reported_partner_count"]==0
    path=base/"partner_inbound_requirements_latest.json"
    path.write_text(json.dumps(_reviewed_leadbank_claim()))
    path.chmod(0o644)
    with pytest.raises(RelationshipEvidenceError,match="not_private"):
        build(root)
    path.chmod(0o600)
    with pytest.raises(RelationshipEvidenceError,match="unknown_or_duplicate_partner_terms"):
        build(root)  # Fixture lacks the required LeadBank canonical relationship


def test_network_public_posts_distinguish_buyers_from_sellers():
    from empire_os.commercial_relationship_registry import classify_publisher_demand_post
    assert classify_publisher_demand_post(
        "We are actively buying inbound calls in roofing and HVAC. Looking for publishers."
    ) == "PUBLIC_PUBLISHER_RECRUITMENT_CLAIM"
    assert classify_publisher_demand_post(
        "Customer-initiated inbound calls available. We are offering inbound calls, looking for buyers."
    ) == "PUBLIC_CALL_SUPPLY_PITCH"
    assert classify_publisher_demand_post(
        "We are actively buying calls and also looking for buyers for our calls."
    ) == "MIXED_BUY_AND_SELL_CLAIMS"
    assert classify_publisher_demand_post(
        "We help home-services businesses grow their customer base."
    ) == "UNCLASSIFIED_NETWORK_PROMOTION"
    assert classify_publisher_demand_post(
        "We are not buying calls at the moment."
    ) == "UNCLASSIFIED_NETWORK_PROMOTION"


def _reviewed_known_company_public_post():
    return {
        "schema_version":"empire.public_network_demand_review.v1",
        "origin":"human_reviewed_public_business_sources",
        "observations":[{
            "entity_key":"newbuyer.com",
            "source_url":"https://www.linkedin.com/company/newbuyer",
            "official_site_evidence_url":"https://newbuyer.com/about",
            "observed_date":"2026-10-10",
            "post_excerpt":"We are actively buying home services calls, and looking for reliable publishers with genuine roofing traffic.",
            "attribution_type":"COMPANY_PAGE",
            "caution_codes":["POST_PUBLICATION_DATE_NOT_INDEPENDENTLY_VERIFIED"],
        }],
    }


def test_known_company_recruiting_post_enriches_existing_record_not_buyer_count():
    from empire_os.commercial_relationship_registry import attach_known_company_public_demand
    src,queue,qual=sources()
    report=reconcile(src,queue,qual,now=datetime(2026,10,10,1,0,tzinfo=timezone.utc))
    original_count=report["relationship_count"]
    stage=next(x["stage"] for x in report["relationships"] if x["entity_key"]=="no-reply")
    out=attach_known_company_public_demand(report,_reviewed_known_company_public_post())
    pulse=out["known_company_public_demand_review"]
    assert pulse["reviewed_known_companies"]==1
    assert pulse["explicit_publisher_recruitment_claims"]==1
    assert pulse["verified_new_buyers"]==0
    assert pulse["verified_call_capacity"]==0
    assert pulse["rows"][0]["previous_outreach_observed"] is True
    assert pulse["rows"][0]["recontact_requires_suppression_and_founder_review"] is True
    assert pulse["rows"][0]["post_publication_date_verified"] is False
    assert out["relationship_count"]==original_count
    assert next(x["stage"] for x in out["relationships"] if x["entity_key"]=="no-reply")==stage
    assert out["outbound_authorized"] is False


@pytest.mark.parametrize("mutation",[
    lambda d:d["observations"][0].update(entity_key="not-in-CRM.com"),
    lambda d:d["observations"][0].update(source_url="https://linkedin.com.evil.net/a"),
    lambda d:d["observations"][0].update(official_site_evidence_url="https://newbuyer.com.evil.org/a"),
    lambda d:d["observations"][0].update(observed_date="2026-12-01"),
    lambda d:d["observations"][0].update(post_excerpt="x"),
    lambda d:d["observations"][0].update(traffic_authorized=True),
    lambda d:d["observations"][0].update(caution_codes=["APPROVED_BUYER"]),
    lambda d:d["observations"].append(copy.deepcopy(d["observations"][0])),
])
def test_public_demand_import_rejects_untrusted_or_privileged_evidence(mutation):
    from empire_os.commercial_relationship_registry import attach_known_company_public_demand
    src,queue,qual=sources()
    doc=_reviewed_known_company_public_post()
    mutation(doc)
    with pytest.raises(RelationshipEvidenceError):
        attach_known_company_public_demand(
            reconcile(src,queue,qual,now=datetime(2026,10,10,2,0,tzinfo=timezone.utc)),
            doc,
        )


def test_private_public_company_demand_integrates_without_sending(tmp_path):
    root = tmp_path
    base = root / "runtime/buyer_network_intelligence"
    base.mkdir(parents=True)
    src, queue, qual = sources()
    for name, contents in (
        ("gmail_relationship_evidence_latest.json",src),
        ("candidate_queue_latest.json",queue),
        ("founder_qualification_actions_latest.json",qual),
    ):
        f=base/name
        f.write_text(json.dumps(contents))
        f.chmod(0o600)
    file=base/"known_company_public_demand_review_latest.json"
    file.write_text(json.dumps(_reviewed_known_company_public_post()))
    file.chmod(0o644)
    with pytest.raises(RelationshipEvidenceError,match="not_private"):
        build(root)
    file.chmod(0o600)
    result=build(root)
    data=result["known_company_public_demand_review"]
    assert data["reviewed_known_companies"] == 1
    assert data["verified_new_buyers"] == 0
    assert result["relationship_count"] == 5
    assert result["outbound_authorized"] is False
    assert result["outbound_sent"] is False
    # Evidence attaches to the original named company, not a new CRM row.
    record=next(x for x in result["relationships"] if x["entity_key"]=="no-reply")
    assert record["public_buying_pulse_review"]["domain"] == "newbuyer.com"
    assert record["stage"] == "CONTACTED_AWAITING_RESPONSE"


def test_founder_review_queue_is_complete_and_draft_only():
    source, queue, qualification = sources()
    for i in range(35):
        source['threads'].append(row(
            f'pending-{i}', f'pending-{i}.example.com', f'{i + 100:016x}',
            outbound='2026-09-25T12:00:00Z',
        ))
    result = reconcile(source, queue, qualification, now=NOW)
    review = result['founder_action_queue']
    assert result['founder_review_required_count'] == len(review)
    assert len(review) > 25
    assert result['founder_action_queue_truncated'] is False
    assert all(item['outbound_authorized'] is False for item in review)
    assert result['founder_actions_are_draft_only'] is True
    assert result['next_actions_automatic_sends'] is False


def test_founder_reported_external_contact_does_not_forge_email_or_buyer_acceptance():
    from scripts.reconcile_buyer_email_relationships import (
        attach_founder_reported_external_contacts,
    )

    report = reconcile(*sources(), now=NOW)
    evidence = {
        "schema_version": "empire.founder_reported_external_contacts.v1",
        "origin": "founder_direct_confirmation_in_chat",
        "observations": [{
            "domain": "onlydiscovered.com",
            "reported_date": "2026-10-10",
            "direction": "founder_sent_first_enquiry",
            "channel": "external_contact_method_unverified",
            "delivery_confirmed": False,
            "reply_confirmed": False,
            "buyer_programme_approved": False,
            "products_requested": ["PAY_PER_CALL"],
            "future_followup_topic": ["PAY_PER_LEAD", "PAY_PER_CALL"],
            "next_action": "WAIT_FIRST_REPLY_THEN_DISCUSS_PPL_NO_DUPLICATE_INTRODUCTION",
        }],
    }
    attach_founder_reported_external_contacts(report, evidence)
    found = next(r for r in report["relationships"]
                 if r["entity_key"] == "onlydiscovered.com")
    assert found["stage"] == "RESEARCH_ONLY"  # no invented verified send
    assert found["last_outbound_at"] is None
    assert found["next_founder_action"] == (
        "WAIT_FOUNDER_REPORTED_RESPONSE_NO_DUPLICATE_INTRO"
    )
    assert found["founder_reported_external_contact"]["delivery_verified"] is False
    assert found["outbound_authorized"] is False
    assert report["outbound_sent"] is False
    assert report["founder_reported_external_contact_count"] == 1
    evidence["observations"][0]["delivery_confirmed"] = True
    with pytest.raises(RelationshipEvidenceError, match="unsupported_founder_contact_assertion"):
        attach_founder_reported_external_contacts(
            reconcile(*sources(), now=NOW), evidence
        )


def test_dual_format_ppl_and_ppc_require_separate_verified_buyer_authority():
    from empire_os.commercial_relationship_registry import (
        PARTNER_PILOT_SCOPES, partner_technical_review_packet,
    )
    for key, spec in PARTNER_PILOT_SCOPES.items():
        # Even an authenticated publisher reply or public programme terms
        # do not establish a PPL intake, buyer postback or a payable call.
        row = {
            "last_inbound_message_id": "1a125653fbace2d6",
            "gmail_thread_ids": [spec["reviewed_thread"]],
        }
        packet = partner_technical_review_packet(key, spec, row)
        formats = packet["publisher_format_review"]
        assert formats["status"] == "BOTH_FORMATS_PROPOSED_NOT_BUYER_APPROVED"
        assert set(formats).issuperset({"PAY_PER_CALL", "PAY_PER_LEAD"})
        call = formats["PAY_PER_CALL"]
        lead = formats["PAY_PER_LEAD"]
        assert call["partner_specific_offer_confirmed"] is False
        assert call["billable_call_duration_and_rules"] is None
        assert call["verified_number_and_route"] is False
        assert call["live_call_traffic_enabled"] is False
        assert lead["partner_specific_offer_confirmed"] is False
        assert lead["lead_price_exclusive_or_shared_terms"] is None
        assert lead["accepted_lead_and_duplicate_rules"] is None
        assert lead["approved_lead_field_and_api_contract"] is None
        assert lead["consumer_disclosure_and_consent_approved"] is False
        assert lead["canonical_empiredb_consumer_intake_verified"] is False
        assert lead["buyer_acceptance_and_rejection_receipts_verified"] is False
        assert lead["live_form_capture_enabled"] is False
        assert lead["lead_delivery_enabled"] is False
        assert formats["cross_format_same_consumer_deduplication_verified"] is False
        assert formats["double_monetization_authorized"] is False
        assert formats["launch_authorized"] is False
        assert packet["selected_partner_offer_format"] is None
        assert packet["traffic_enabled"] is False
        assert packet["execution_authority"] == "NONE"


@pytest.mark.parametrize("direction,channel,action", [
    ("founder_sent_first_enquiry", "website_contact_form",
     "WAIT_FIRST_REPLY_THEN_DISCUSS_PPL_NO_DUPLICATE_INTRODUCTION"),
    ("founder_submitted_application", "website_application_form",
     "AWAIT_APPLICATION_RESPONSE_NO_DUPLICATE_CONTACT"),
])
def test_founder_web_form_and_application_are_not_duplicate_email_or_buyer_approval(
    direction, channel, action,
):
    from scripts.reconcile_buyer_email_relationships import (
        attach_founder_reported_external_contacts,
    )
    report = reconcile(*sources(), now=NOW)
    item = {
        "domain": "onlydiscovered.com",
        "reported_date": "2026-10-10",
        "direction": direction,
        "channel": channel,
        "delivery_confirmed": False,
        "reply_confirmed": False,
        "buyer_programme_approved": False,
        "products_requested": ["PAY_PER_CALL"],
        "future_followup_topic": ["PAY_PER_LEAD", "PAY_PER_CALL"],
        "next_action": action,
    }
    evidence = {
        "schema_version": "empire.founder_reported_external_contacts.v1",
        "origin": "founder_direct_confirmation_in_chat",
        "observations": [item],
    }
    attach_founder_reported_external_contacts(report, evidence)
    found = next(x for x in report["relationships"]
                 if x["entity_key"] == "onlydiscovered.com")
    assert found["stage"] == "RESEARCH_ONLY"
    assert found["last_outbound_at"] is None
    assert found["gmail_thread_ids"] == []
    assert found["founder_reported_external_contact"]["channel"] == channel
    assert found["founder_reported_external_contact"]["next_action"] == action
    assert found["founder_reported_external_contact"]["delivery_verified"] is False
    assert found["outbound_authorized"] is False
    assert found["commercial_buyer_approved"] is False
    assert report["founder_reported_external_contact_count"] == 1
    # A founder report must never be upgraded to independent delivery proof.
    item["delivery_confirmed"] = True
    with pytest.raises(RelationshipEvidenceError, match="unsupported_founder_contact_assertion"):
        attach_founder_reported_external_contacts(
            reconcile(*sources(), now=NOW), evidence
        )

def test_founder_do_not_pursue_overrides_stale_gmail_followup():
    src, queue, qual = sources()
    src['threads'].append(row('callvox.pro', 'callvox.pro', 'aaaaaaaaaaaa1111',
                              outbound='2026-10-09T15:00:00Z'))
    queue['candidates'].append({'domain': 'callvox.pro', 'status': 'WATCH'})
    queue['candidate_count'] = len(queue['candidates'])
    report = reconcile(src, queue, qual, now=NOW,
                       do_not_pursue_domains=frozenset({'callvox.pro'}))
    records = [x for x in report['relationships'] if x['entity_key']=='callvox.pro']
    assert len(records) == 1
    held = records[0]
    assert held['do_not_pursue'] is True
    assert held['stage'] == 'EVIDENCE_HOLD'
    assert held['next_founder_action'] == 'DO_NOT_PURSUE_NO_CONTACT'
    assert held['founder_review_required'] is False
    assert held['auto_send_authorized'] is False
    assert all(x['entity_key'] != 'callvox.pro' for x in report['founder_action_queue'])


def test_inquirly_replied_and_sent_proposal_is_fourth_distinct_zero_authority_pilot():
    from empire_os.commercial_relationship_registry import (
        PARTNER_PILOT_SCOPES, PARTNER_LAUNCH_GATES,
    )
    src,queue,qual=sources()
    for key,domain in (
        ("leadbank","alliancevs.io"),("validated","validatedlg.ai"),
        ("connexis","connex.is"),("inquirly.com","inquirly.com"),
    ):
        scope=PARTNER_PILOT_SCOPES[key]
        relation=row(key,domain,scope["reviewed_thread"],
                     inbound="2026-10-12T15:42:33Z",
                     outbound="2026-10-12T17:38:47Z")
        if key=="inquirly.com":
            relation["last_inbound_message_id"]="1a130c837466d185"
            relation["last_outbound_message_id"]="1a1313213d12d010"
        src["threads"].append(relation)
    now=datetime(2026,10,12,18,40,tzinfo=timezone.utc)
    report=reconcile(src,queue,qual,now=now)
    pilots={p["entity_key"]:p for p in report["partner_pilot_readiness_queue"]}
    assert set(pilots)==set(PARTNER_PILOT_SCOPES)
    state=pilots["inquirly.com"]
    assert state["current_next_partner_task"]=="AWAIT_INQUIRLY_NJ_BUYBOX_LANDING_REVIEW_NO_REPEAT"
    assert state["gate_count_verified"]==0
    assert state["gate_count_total"]==len(PARTNER_LAUNCH_GATES)
    assert all(v is False for v in state["activation_gates"].values())
    assert state["single_pass_buyer_intake"]["repeat_full_request_blocked"] is True
    packet=state["technical_review_packet"]
    assert packet["partner_tracking_number"] is None
    assert packet["routing_destination_or_sip_endpoint"] is None
    assert packet["verified_target_zips_or_postcodes"] is None
    assert packet["verified_payout_and_settlement"] is None
    assert packet["lead_smart_route_or_number_inherited"] is False
    assert packet["traffic_enabled"] is False
    assert packet["publisher_format_review"]["launch_authorized"] is False
    assert packet["publisher_format_review"]["PAY_PER_LEAD"]["lead_delivery_enabled"] is False
    assert state["live_traffic_authorized"] is False
    assert state["outbound_authorized"] is False


# 17 October reviewed Gmail replies: stop asking questions that have already
# been answered; retain explicit buyer/permission/financial gates.
def _reviewed_live_reply_sources():
    src, queue, qual = sources()
    now = datetime(2026, 10, 17, 18, 15, tzinfo=timezone.utc)
    src["captured_at"] = now.isoformat()
    lead = src["threads"][0]
    lead["gmail_thread_id"] = "1a0d9ce883c87d4a"
    lead["last_inbound_message_id"] = "1a145b32d742f3b1"
    lead["last_inbound_at"] = "2026-10-16T17:12:09+00:00"
    lead["last_outbound_at"] = "2026-10-16T17:05:46+00:00"
    lead["last_outbound_message_id"] = "1a145ad4636ac390"
    src["threads"].append({
        **row(
            "inquirly.com", "inquirly.com", "1a0d9ef44c7f77d0",
            inbound="2026-10-16T15:06:05+00:00",
            outbound="2026-10-16T10:43:45+00:00",
            company="inquirly.com",
        ),
        "last_inbound_message_id": "1a14540463907582",
        "last_outbound_message_id": "1a1444f864718408",
    })
    return src, queue, qual, now


def test_latest_real_buyer_replies_replace_obsolete_contact_actions():
    src, queue, qual, now = _reviewed_live_reply_sources()
    d = reconcile(src, queue, qual, now=now)
    rows = {x["entity_key"]: x for x in d["relationships"]}
    lead = rows["lead-smart"]
    assert lead["stage"] == "INBOUND_REVIEW_REQUIRED"
    assert lead["next_founder_action"] == (
        "PREPARE_EXISTING_SUPERVISED_ROOFING_PILOT_NO_DUPLICATE_TEST"
    )
    assert lead["reviewed_buyer_reply_disposition"]["status"] == (
        "BUYER_REPORTS_RECORDING_TEST_COMPLETE"
    )
    assert lead["reviewed_buyer_reply_disposition"]["payable_event_verified"] is False
    assert lead["founder_review_required"] is True
    inquirly = rows["inquirly.com"]
    assert inquirly["next_founder_action"] == (
        "DEFER_INQUIRLY_UNTIL_VERIFIED_TRAFFIC_NO_REPEAT_REQUEST"
    )
    assert inquirly["founder_review_required"] is False
    assert inquirly["reviewed_buyer_reply_disposition"]["live_traffic_authorized"] is False
    pilots = {x["entity_key"]: x for x in d["partner_pilot_readiness_queue"]}
    assert pilots["inquirly.com"]["current_next_partner_task"] == inquirly["next_founder_action"]
    assert pilots["inquirly.com"]["activation_stage"] == "DEFERRED_PENDING_ESTABLISHED_TRAFFIC"
    assert all(v is False for v in pilots["inquirly.com"]["activation_gates"].values())
    assert d["outbound_authorized"] is False
    assert d["outbound_sent"] is False


def test_reviewed_buyer_reply_override_fails_closed_if_source_changes():
    src, queue, qual, now = _reviewed_live_reply_sources()
    src["threads"][0]["last_inbound_message_id"] = "1a145b32d742f3b0"
    src["threads"][-1]["gmail_thread_id"] = "1a0d9ef44c7f77d1"
    rows = {x["entity_key"]: x for x in reconcile(src, queue, qual, now=now)["relationships"]}
    assert rows["lead-smart"]["reviewed_buyer_reply_disposition"] is None
    assert rows["inquirly.com"]["reviewed_buyer_reply_disposition"] is None
    assert rows["lead-smart"]["outbound_authorized"] is False
    assert rows["inquirly.com"]["outbound_authorized"] is False


def test_stale_or_newer_outbound_never_reuses_reviewed_reply_decision():
    src, queue, qual, now = _reviewed_live_reply_sources()
    stale = reconcile(src, queue, qual, now=now + timedelta(days=5))
    rows = {x["entity_key"]: x for x in stale["relationships"]}
    assert rows["lead-smart"]["reviewed_buyer_reply_disposition"] is None
    assert rows["inquirly.com"]["reviewed_buyer_reply_disposition"] is None

    src["threads"][0]["last_outbound_at"] = "2026-10-16T17:30:00+00:00"
    src["threads"][0]["last_outbound_message_id"] = "aaaaaaaaaaaaaaaa"
    rows = {x["entity_key"]: x for x in reconcile(src, queue, qual, now=now)["relationships"]}
    assert rows["lead-smart"]["reviewed_buyer_reply_disposition"] is None


def test_founder_no_contact_hold_beats_even_exact_reviewed_reply():
    src, queue, qual, now = _reviewed_live_reply_sources()
    d = reconcile(
        src, queue, qual, now=now,
        do_not_pursue_domains=frozenset({"leadsmartinc.com", "inquirly.com"}),
    )
    rows = {x["entity_key"]: x for x in d["relationships"]}
    for key in ("lead-smart", "inquirly.com"):
        assert rows[key]["next_founder_action"] == "DO_NOT_PURSUE_NO_CONTACT"
        assert rows[key]["founder_review_required"] is False
        assert rows[key]["outbound_authorized"] is False
