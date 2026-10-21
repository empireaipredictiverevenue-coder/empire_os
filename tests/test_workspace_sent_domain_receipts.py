"""Gmail Workspace SENT-domain metadata gate: no email bodies or send authority."""
from datetime import datetime, timezone, timedelta
import json
import os

import pytest

from empire_os.workspace_sent_domain_receipts import (
    WorkspaceSentHistoryError, capture, read_previous,
)
from empire_os.buyer_network_contact_history_gate import load_context, review
from scripts.refresh_workspace_sent_domain_receipts import run

NOW = datetime(2026, 10, 21, 21, 30, tzinfo=timezone.utc)


def message(domain="ringpartner.com", ident="1a155e9d02106ee0",
            sender="Phillip <phil@empire-ai.co.uk>", when=NOW):
    return {
        "id": "workspace:sent:" + ident, "provider": "google_workspace",
        "status": "sent",
        "from": sender, "to": ["Publisher <contact@" + domain + ">"],
        "mailbox_internal_date": when.isoformat(),
        "subject": "Never persist subject",
        "text": "Never persist body snippet",
    }


def test_bounded_sent_scan_records_domain_not_body_or_email_address():
    doc = capture([message()], now=NOW)
    assert doc["domain_count"] == 1
    assert doc["domains"][0]["domain"] == "ringpartner.com"
    assert doc["outbound_authorized"] is False
    assert doc["delivery_verified"] is False
    assert doc["complete_mailbox_history_verified"] is False
    text = json.dumps(doc)
    assert "Never persist" not in text
    assert "contact@ringpartner.com" not in text
    assert "phil@empire-ai.co.uk" in text  # fixed authenticated account only


def test_sent_history_merges_monotonically_without_duplicate_contacts():
    first = capture([message()], now=NOW)
    second = capture([message("leadsbycall.com", "1a16000000000000")],
                     previous=first, now=NOW + timedelta(minutes=1))
    assert sorted(x["domain"] for x in second["domains"]) == ["leadsbycall.com","ringpartner.com"]
    third = capture([message()], previous=second, now=NOW+timedelta(minutes=2))
    assert third["domain_count"] == 2


def test_invalid_label_sender_or_future_timestamp_never_promoted():
    bad = message()
    bad["status"] = "received"
    with pytest.raises(WorkspaceSentHistoryError):
        capture([bad], now=NOW)
    assert capture([message(sender="hacker@other.example")],now=NOW)["domain_count"] == 0
    with pytest.raises(WorkspaceSentHistoryError):
        capture([message(when=NOW + timedelta(hours=2))],now=NOW)


def test_private_history_integrity_and_domain_gate(tmp_path):
    doc = capture([message()], now=NOW)
    prior = tmp_path/"workspace_sent_domain_receipts_latest.json"
    prior.write_text(json.dumps(doc))
    os.chmod(prior, 0o600)
    assert read_previous(prior)["domain_count"] == 1
    registry = tmp_path/"registry.json"
    registry.write_text(json.dumps({
        "schema_version":"empire.commercial_relationship_registry.v1",
        "relationships":[{"entity_key":"ringpartner.com","identity_domains":["ringpartner.com"]}],
        "gmail_snapshot_fresh":False,
    }))
    external = tmp_path/"external.json"
    external.write_text(json.dumps({
        "schema_version":"empire.founder_reported_external_contacts.v1",
        "observations":[],
    }))
    context=load_context(registry, external, prior)
    item=review("ringpartner.com",context)
    assert item["state"] == "WORKSPACE_SENT_ALREADY_CONTACTED"
    assert item["outbound_authorized"] is False
    assert item["last_outbound_at"] == NOW.isoformat()
    os.chmod(prior, 0o644)
    assert read_previous_if_invalid(prior) == "WORKSPACE_SENT_SOURCE_UNSAFE"


def read_previous_if_invalid(path):
    try:
        read_previous(path)
    except WorkspaceSentHistoryError as exc:
        return str(exc)
    return ""


def test_opt_out_precedes_workspace_message(tmp_path):
    snapshot = tmp_path/"workspace.json"
    doc=capture([message()],now=NOW)
    snapshot.write_text(json.dumps(doc))
    os.chmod(snapshot,0o600)
    registry=tmp_path/"registry.json"
    registry.write_text(json.dumps({
       "schema_version":"empire.commercial_relationship_registry.v1",
       "gmail_snapshot_fresh":False,
       "relationships":[{"entity_key":"ringpartner.com","do_not_pursue":True}],
    }))
    ext=tmp_path/"external.json"
    ext.write_text(json.dumps({"schema_version":"empire.founder_reported_external_contacts.v1","observations":[]}))
    assert review("ringpartner.com",load_context(registry,ext,snapshot))["state"]=="DO_NOT_PURSUE"


class FakeProvider:
    configured=True
    def __init__(self,rows):
        self.rows=rows
        self.calls=[]
    def list_sent(self,*,limit):
        self.calls.append(limit)
        return self.rows


def test_runner_preview_never_writes_or_sends(tmp_path):
    output=tmp_path/"not-written.json"
    provider=FakeProvider([message()])
    result=run(provider=provider,write=False,output=output)
    assert result["status"]=="PASS"
    assert result["outbound_sent"] is False
    assert result["database_writes"] is False
    assert not output.exists()
    assert provider.calls==[20]
