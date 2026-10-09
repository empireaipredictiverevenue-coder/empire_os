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
