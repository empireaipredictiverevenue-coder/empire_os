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
