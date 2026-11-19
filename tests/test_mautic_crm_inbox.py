"""Synthetic durable canonical inbox + HTTP ingress contract. No EmpireDB writes."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.mautic_crm_inbox import (
    PostgresMauticEventInbox, MauticInboxUnavailable, TABLE, ROLE,
)
from empire_os.mautic_crm_integration import (
    MauticSource, create_mautic_crm_preview_router,
)

TENANT = "00000000-0000-0000-0000-000000000101"
OTHER = "00000000-0000-0000-0000-000000000102"
PROSPECT = "00000000-0000-0000-0000-000000000201"
NOW = datetime(2026, 11, 19, 11, 0, tzinfo=timezone.utc)
SECRET = b"test-signature-secret-not-for-production"
DIGEST = "a" * 64
SOURCE_ID = "mautic-test"


class Cursor:
    def __init__(self, db):
        self.db = db
        self.row = None

    def __enter__(self): return self
    def __exit__(self, *_): return False

    def execute(self, sql, args=None):
        self.db["queries"].append((sql,args))
        if sql.startswith("SELECT current_database()"):
            self.row = self.db.get("privileges", (
                "empiredb", True, False, False, False,
            ))
        elif sql.startswith("SELECT public.empire_current_tenant_id()"):
            self.row = (self.db.get("tenant", TENANT),)
        elif sql.startswith("INSERT INTO "):
            assert TABLE in sql
            assert "ON CONFLICT DO NOTHING" in sql
            assert len(args) == 8
            key = args[:3]
            if key in self.db["receipts"]:
                self.row = None
            else:
                self.db["receipts"][key] = (args[3],*args[4:])
                self.row = (args[2],)
        elif sql.startswith("SELECT prospect_id::text"):
            assert TABLE in sql
            self.row = self.db["receipts"].get(args)
            if self.db.get("readback_broken"):
                self.row = None
        else:
            assert sql.startswith("SET "), sql

    def fetchone(self): return self.row


class Conn:
    def __init__(self, db): self.db = db
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def cursor(self): return Cursor(self.db)


def inbox(db):
    return PostgresMauticEventInbox(
        "FAKE_DSN_ONLY", authenticated_tenant_id=TENANT,
        connect_factory=lambda _dsn: Conn(db),
    )


def review(fingerprint=DIGEST):
    return {
        "prospect_id": PROSPECT,
        "event_evidence_hmac": fingerprint,
        "source_event": "mautic.lead_channel_subscription_changed",
        "signal": "SUPPRESSION_REVIEW_REQUIRED",
        "timestamp_state": "RECENT_OBSERVED",
        "canonical_journey_segment": "contact_hold",
    }


def reserve(writer, record=None, **overrides):
    options = {
        "tenant_id": TENANT, "source_id": SOURCE_ID,
        "evidence_hmacs": [DIGEST], "reviews": [record or review()],
        "now": NOW,
    }
    options.update(overrides)
    return writer.reserve_new(**options)


def test_canonical_inbox_writes_only_allowlisted_signals_and_committed_readback():
    db = {"queries": [], "receipts": {}}
    writer = inbox(db)
    assert reserve(writer) == {DIGEST}
    assert reserve(writer) == set()
    assert len(db["receipts"]) == 1
    assert db["receipts"][(TENANT,SOURCE_ID,DIGEST)] == (
        PROSPECT, "mautic.lead_channel_subscription_changed",
        "SUPPRESSION_REVIEW_REQUIRED", "RECENT_OBSERVED", "contact_hold",
    )
    sql = "\n".join(query for query,_ in db["queries"])
    assert "SET LOCAL ROLE " + ROLE in sql
    assert "SELECT public.empire_current_tenant_id()" in sql
    assert "SET TRANSACTION READ ONLY" in sql
    assert "SELECT prospect_id::text" in sql
    assert "UPDATE " + TABLE not in sql
    assert "DELETE FROM " + TABLE not in sql


@pytest.mark.parametrize("overrides", [
    {"privileges": ("empiredb", False, False, False, False)},
    {"privileges": ("empiredb", True, True, False, False)},
    {"privileges": ("empiredb", True, False, True, False)},
    {"privileges": ("empiredb", True, False, False, True)},
    {"tenant": OTHER},
    {"privileges": ("unauthorized_db", True, False, False, False)},
])
def test_dedicated_role_or_db_tenant_mismatch_refused(overrides):
    db = {"queries": [], "receipts": {}, **overrides}
    with pytest.raises(MauticInboxUnavailable):
        reserve(inbox(db))
    assert db["receipts"] == {}


@pytest.mark.parametrize("overrides", [
    {"tenant_id": OTHER},
    {"source_id": "bad/source"},
    {"evidence_hmacs": ["X"*64]},
    {"evidence_hmacs": []},
])
def test_bad_receipts_rejected_before_database_io(overrides):
    db = {"queries": [], "receipts": {}}
    with pytest.raises(MauticInboxUnavailable):
        reserve(inbox(db), **overrides)
    assert db["queries"] == []


@pytest.mark.parametrize("tampered", [
    {"prospect_id": "not-a-uuid"},
    {"source_event": "mautic.attempt_execute"},
    {"source_event": ["mautic.form_on_submit"]},
    {"signal": {"force": "SEND_NOW"}},
    {"signal": "SEND_NOW"},
    {"timestamp_state": "unknown"},
    {"canonical_journey_segment": "purchase_paid"},
    {"event_evidence_hmac": "different"},
])
def test_untrusted_event_values_refused_before_sql(tampered):
    db = {"queries": [], "receipts": {}}
    record = {**review(), **tampered, "email": "not-for-db@example.test"}
    with pytest.raises(MauticInboxUnavailable):
        reserve(inbox(db), record=record)
    assert db["queries"] == []


def test_failed_committed_readback_is_not_acknowledged():
    db = {"queries": [], "receipts": {}, "readback_broken": True}
    with pytest.raises(MauticInboxUnavailable, match="unavailable"):
        reserve(inbox(db))
    assert len(db["receipts"]) == 1  # commit may have occurred
    # A retry only receives a successful acknowledgement after readback works.
    db["readback_broken"] = False
    assert reserve(inbox(db)) == set()


def test_canonical_schema_is_prepared_only_and_tenant_bound():
    root = Path(__file__).resolve().parents[1]
    sql = (root / "docs/integrations/sql/MAUTIC_CRM_EVENT_INBOX_PREPARED_ONLY_20261119.sql").read_text()
    assert "PREPARED-ONLY" in sql and "DO NOT APPLY" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "tenant_id=public.empire_current_tenant_id()" in sql
    assert "PRIMARY KEY (tenant_id,source_id,event_evidence_hmac)" in sql
    assert "GRANT SELECT,INSERT" in sql
    assert "CREATE TABLE " + TABLE in sql
    assert "REVOKE ALL" in sql
    for forbidden in (
        "GRANT UPDATE", "GRANT DELETE", "CREATE USER",
        "CREATE LOGIN", "ALTER ROLE", "TO empiredb_app;",
        "SEND EMAIL", "CREATE TRIGGER",
    ):
        assert forbidden not in sql


class FakeCrm:
    tenant_id = TENANT
    def prospect(self, prospect_id):
        if prospect_id != PROSPECT:
            return None
        return {
            "tenant_id": TENANT,
            "prospect_id": PROSPECT,
            "prospect_status": "suppressed",
            "conversation_state": "engaged",
        }


def make_client(writer, *, bindings=None):
    configured = MauticSource(
        source_id=SOURCE_ID, tenant_id=TENANT,
        webhook_secret=SECRET,
        contact_bindings=bindings if bindings is not None else {
            42: {"tenant_id": TENANT, "prospect_id": PROSPECT},
        },
    )
    app = FastAPI()
    app.include_router(create_mautic_crm_preview_router(
        resolve_source=lambda source: configured if source == SOURCE_ID else None,
        resolve_tenant_reader=lambda tenant: FakeCrm() if tenant == TENANT else None,
        receipt_journal=writer,
        allow_synthetic_test_reader=True,  # Never set in a real app.
        now_provider=lambda: NOW,
    ))
    return TestClient(app)


def payload(contact_id=42):
    raw = json.dumps({
        "mautic.lead_channel_subscription_changed": [
            {"contact": {"id": contact_id, "email": "sensitive@example.test"},
             "channel": "email", "new_status": "unsubscribed",
             "timestamp": NOW.isoformat()}
        ]
    }).encode("utf-8")
    sig = base64.b64encode(hmac.new(SECRET, raw, hashlib.sha256).digest()).decode()
    return raw, {"Content-Type":"application/json", "Webhook-Signature": sig}


def test_complete_http_to_canonical_event_inbox_with_readback():
    db = {"queries": [], "receipts": {}}
    client = make_client(inbox(db))
    raw, headers = payload()
    path = "/v1/revenue-crm/integrations/mautic/mautic-test/events/preview"
    first = client.post(path, content=raw, headers=headers)
    assert first.status_code == 200, first.text
    result = first.json()
    assert result["new_events"] == 1
    assert result["canonical_inbox_readback_verified"] is True
    assert result["durable_staging_replay_journal"] is False
    assert result["journey_reviews"][0]["canonical_journey_segment"] == "contact_hold"
    assert result["send_authorized"] is False
    assert "sensitive@example.test" not in first.text
    assert len(db["receipts"]) == 1
    replay = client.post(path, content=raw, headers=headers)
    assert replay.status_code == 200
    assert replay.json()["new_events"] == 0
    assert replay.json()["duplicate_events"] == 1


def test_production_inbox_does_not_acknowledge_unbound_contact():
    db = {"queries": [], "receipts": {}}
    client = make_client(inbox(db))
    raw, headers = payload(contact_id=999)
    result = client.post(
        "/v1/revenue-crm/integrations/mautic/mautic-test/events/preview",
        content=raw, headers=headers,
    )
    assert result.status_code == 503
    assert result.json()["detail"] == "mautic_contact_binding_unavailable"
    assert db["receipts"] == {}
