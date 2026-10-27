"""Prior founder personal-Gmail SENT records prevent repeat introductions."""
from datetime import datetime, timezone
from pathlib import Path
import json
import os

import pytest

from empire_os.buyer_network_contact_history_gate import load_context, review
from empire_os.buyer_personal_gmail_sent_history import (
    SCHEMA, SOURCE, MAILBOX, read_personal_gmail_sent_receipts,
)

NOW = datetime(2026, 10, 27, 17, 0, tzinfo=timezone.utc)


def receipt(domain, recipient, message_id, thread_id, sent_at):
    return {
        "domain": domain, "recipient": recipient,
        "provider_sent_message_id": message_id,
        "provider_thread_id": thread_id,
        "sent_at": sent_at, "provider_label": "SENT",
        "delivery_verified": False, "buyer_approved": False,
        "outbound_authorized": False,
    }


def source(*rows):
    return {
        "schema_version": SCHEMA, "source": SOURCE,
        "mailbox": MAILBOX, "outbound_authorized": False,
        "buyer_approved": False, "receipts": list(rows),
    }


def setup(tmp_path, payload):
    registry = tmp_path / "commercial_relationship_registry_latest.json"
    external = tmp_path / "founder_reported_external_contacts_latest.json"
    evidence = tmp_path / "personal_gmail_historical_sent_20261027.json"
    registry.write_text(json.dumps({
        "schema_version": "empire.commercial_relationship_registry.v1",
        "gmail_snapshot_fresh": False, "relationships": [],
    }))
    external.write_text(json.dumps({
        "schema_version": "empire.founder_reported_external_contacts.v1",
        "observations": [],
    }))
    evidence.write_text(json.dumps(payload))
    evidence.chmod(0o600)
    return registry, external, evidence


def test_exact_two_proven_personal_gmail_sends_stop_duplicate_initial_outreach(tmp_path):
    rows = [
        receipt("advertisingresults.com", "email@advertisingresults.com",
                "1a134add2f0e832f", "1a134ab6ab1988d1",
                "2026-10-13T09:52:49+00:00"),
        receipt("summitleads.ai", "team@summitleads.ai",
                "1a1347d4bf3f29c4", "1a1347d4bf3f29c4",
                "2026-10-13T08:59:48+00:00"),
    ]
    reg, ext, path = setup(tmp_path, source(*rows))
    asserted = read_personal_gmail_sent_receipts(path, now=NOW)
    assert set(asserted) == {"advertisingresults.com", "summitleads.ai"}
    ctx = load_context(reg, ext, tmp_path / "no_workspace.json")
    assert ctx["available"] is True
    for domain in asserted:
        item = review(domain, ctx)
        assert item["state"] == "PERSONAL_GMAIL_SENT_ALREADY_CONTACTED"
        assert item["personal_gmail_prior_sent_receipt"] is True
        assert item["outbound_authorized"] is False
        assert item["last_outbound_at"] == asserted[domain]["sent_at"]
    assert review("uncontacted-example.com", ctx)["state"] == "UNKNOWN_HISTORY"


@pytest.mark.parametrize("change", [
    {"provider_label": "DRAFT"},
    {"buyer_approved": True},
    {"outbound_authorized": True},
    {"delivery_verified": True},
    {"provider_sent_message_id": "bad"},
    {"recipient": "wrong@example.com"},
    {"sent_at": "2030-01-01T00:00:00+00:00"},
    {"sent_at": "2026-10-13T09:52:49"},
])
def test_forged_or_unverifiable_proofs_fail_closed(tmp_path, change):
    first = receipt("advertisingresults.com", "email@advertisingresults.com",
                    "1a134add2f0e832f", "1a134ab6ab1988d1",
                    "2026-10-13T09:52:49+00:00")
    first.update(change)
    reg, ext, path = setup(tmp_path, source(first))
    with pytest.raises(ValueError, match="PERSONAL_GMAIL_SENT_"):
        read_personal_gmail_sent_receipts(path, now=NOW)
    ctx = load_context(reg, ext, tmp_path / "no_workspace.json")
    assert ctx["available"] is False
    assert review("advertisingresults.com", ctx)["state"] == "SOURCE_UNAVAILABLE"


def test_missing_source_is_unknown_not_cleared(tmp_path):
    reg, ext, path = setup(tmp_path, source())
    path.unlink()
    ctx = load_context(reg, ext, tmp_path / "no_workspace.json")
    assert ctx["available"] is True
    assert review("advertisingresults.com", ctx)["state"] == "UNKNOWN_HISTORY"
    assert review("advertisingresults.com", ctx)["outbound_authorized"] is False


def test_public_mode_or_symlink_proof_is_rejected(tmp_path):
    reg, ext, path = setup(tmp_path, source(
        receipt("advertisingresults.com", "email@advertisingresults.com",
                "1a134add2f0e832f", "1a134ab6ab1988d1",
                "2026-10-13T09:52:49+00:00")))
    path.chmod(0o644)
    assert load_context(reg, ext, tmp_path / "no_workspace.json")["available"] is False
    path.chmod(0o600)
    moved = tmp_path / "secret.json"
    path.rename(moved)
    path.symlink_to(moved)
    assert load_context(reg, ext, tmp_path / "no_workspace.json")["available"] is False


def test_opt_out_wins_over_historical_sent_receipt(tmp_path):
    reg, ext, path = setup(tmp_path, source(
        receipt("advertisingresults.com", "email@advertisingresults.com",
                "1a134add2f0e832f", "1a134ab6ab1988d1",
                "2026-10-13T09:52:49+00:00")))
    d=json.loads(reg.read_text())
    d["relationships"]=[{"entity_key":"advertisingresults.com",
                         "do_not_pursue":True}]
    reg.write_text(json.dumps(d))
    ctx=load_context(reg,ext,tmp_path/"no_workspace.json")
    assert review("advertisingresults.com",ctx)["state"]=="DO_NOT_PURSUE"
    assert review("advertisingresults.com",ctx)["outbound_authorized"] is False


def test_exact_verified_namastey_site_mail_domain_binding_holds_repeat(tmp_path):
    reg, ext, path = setup(tmp_path, source(
        receipt("namasteymail.com", "namastey@namasteymail.com",
                "1a12771d14fd8d2e", "1a0d9de9548a5945",
                "2026-10-10T20:12:13+00:00"),
    ))
    ctx=load_context(reg,ext,tmp_path/"no_workspace.json")
    for domain in ("namasteymail.com","namasteynetwork.com"):
        item=review(domain,ctx)
        assert item["state"]=="PERSONAL_GMAIL_SENT_ALREADY_CONTACTED"
        assert item["last_outbound_at"]=="2026-10-10T20:12:13+00:00"
        assert item["outbound_authorized"] is False
    assert ctx["personal_prior_sent"]["namasteynetwork.com"]["source"] == "FOUNDER_REVIEWED_PUBLIC_CONTACT_DOMAIN_ALIAS"
    assert review("namastey-other.com",ctx)["state"]=="UNKNOWN_HISTORY"


def test_mail_domain_alias_without_verified_sent_receipt_remains_unknown(tmp_path):
    reg,ext,path=setup(tmp_path,source())
    ctx=load_context(reg,ext,tmp_path/"no_workspace.json")
    assert review("namasteynetwork.com",ctx)["state"]=="UNKNOWN_HISTORY"
    assert review("namasteynetwork.com",ctx)["outbound_authorized"] is False


def test_namastey_opt_out_still_overrides_mail_domain_alias(tmp_path):
    reg,ext,path=setup(tmp_path,source(
        receipt("namasteymail.com","namastey@namasteymail.com",
                "1a12771d14fd8d2e","1a0d9de9548a5945",
                "2026-10-10T20:12:13+00:00"),
    ))
    d=json.loads(reg.read_text())
    d["relationships"]=[{"entity_key":"namasteynetwork.com","do_not_pursue":True}]
    reg.write_text(json.dumps(d))
    ctx=load_context(reg,ext,tmp_path/"no_workspace.json")
    assert review("namasteynetwork.com",ctx)["state"]=="DO_NOT_PURSUE"
