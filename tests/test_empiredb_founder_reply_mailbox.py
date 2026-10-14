"""Canonical founder reply viewer: no OAuth, no send, least privileged read."""
from datetime import datetime, timezone
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.empiredb_founder_reply_mailbox import (
    EmpireDBFounderReplyMailbox, MailboxReadUnavailable,
)
from empire_os.founder_mailbox_api import create_founder_mailbox_router

RID = "962fe73d-8b95-4335-a2ed-5e388803c8ad"
IID = "bd599e22-9f9e-4520-9c88-99cdb1d021c6"
STAMP = datetime(2026, 10, 13, 18, 10, tzinfo=timezone.utc)
IN_ROW = (uuid.UUID(RID), uuid.UUID(IID), "Founder Tester <person@example.org>",
          "reply@mail.empire-ai.co.uk", "Re: Founder hello", "This is a test reply", STAMP,
          "unclassified", "provider-test-id")
OUT_ROW = (uuid.UUID(IID), "person@example.org", "Founder hello", "Sent body", STAMP,
           "replied")


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed = []
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def execute(self, text, params=None):
        self.executed.append((text, params))
    def fetchall(self):
        return self.rows


class FakeConn:
    def __init__(self, rows):
        self.cur = FakeCursor(rows)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def cursor(self):
        return self.cur


def test_received_replies_only_from_canonical_role_and_never_authorize():
    conn = FakeConn([IN_ROW])
    source = EmpireDBFounderReplyMailbox(dsn="fake-readonly-dsn", connect_factory=lambda *a,**kw: conn)
    messages = source.list_received(limit=2)
    assert len(messages) == 1
    assert messages[0]["id"] == "canonical-reply:" + RID
    assert messages[0]["intent_id"] == IID
    assert messages[0]["body_preview_only"] is True
    assert messages[0]["commercial_buying_intent_verified"] is False
    assert messages[0]["outreach_authorized"] is False
    assert messages[0]["text"] == "This is a test reply"
    assert source.suppression_evidence_complete is False
    assert source.readiness()["scope"] == "CANONICAL_RECORDED_REPLIES_ONLY_NOT_GENERAL_INBOX"
    assert conn.cur.executed[0][0] == "SET TRANSACTION READ ONLY"
    assert conn.cur.executed[1][0] == "SET LOCAL ROLE empire_closer_observer"
    assert conn.cur.executed[2][0].startswith("SET LOCAL statement_timeout")
    assert conn.cur.executed[3][1] == (2,)
    assert "JOIN public.outbound_intents" in conn.cur.executed[3][0]
    assert conn.cur.executed[-1][0] == "ROLLBACK"


def test_only_sent_canonical_intents_not_drafts():
    conn = FakeConn([OUT_ROW])
    source = EmpireDBFounderReplyMailbox(dsn="fake-readonly-dsn", connect_factory=lambda *a,**kw: conn)
    rows = source.list_sent(limit=1)
    assert rows[0]["id"] == "canonical-intent:" + IID
    assert rows[0]["verified_provider_delivery"] is False
    assert rows[0]["outreach_authorized"] is False
    assert "status IN ('sent','delivered','replied')" in conn.cur.executed[3][0]
    assert "recipient" in conn.cur.executed[3][0]
    with pytest.raises(MailboxReadUnavailable, match="CANONICAL_SENT_INTENT_INCOMPLETE"):
        source._sent((*OUT_ROW[:5], "approved"))


def test_missing_reader_credentials_and_limits_fail_closed():
    source = EmpireDBFounderReplyMailbox(dsn="")
    assert source.readiness()["configured"] is False
    with pytest.raises(MailboxReadUnavailable, match="DEDICATED_CANONICAL_REPLY_READER_UNAVAILABLE"):
        source.list_received(limit=1)
    with pytest.raises(MailboxReadUnavailable, match="CANONICAL_REPLY_ROW_LIMIT_REQUIRED"):
        source.list_received(limit=100)
    with pytest.raises(MailboxReadUnavailable, match="CANONICAL_MESSAGE_IDENTIFIER_UNVERIFIED"):
        source.get_received("canonical-reply:'; DELETE FROM outbound_replies")


def test_exact_record_lookup_is_parameterized_and_bounded():
    conn = FakeConn([IN_ROW])
    source = EmpireDBFounderReplyMailbox(dsn="reader", connect_factory=lambda *a,**kw: conn)
    assert source.get_received("canonical-reply:" + RID)["intent_id"] == IID
    assert conn.cur.executed[3][1] == (RID,)
    assert "r.id=%s::uuid" in conn.cur.executed[3][0]


def test_wrong_shape_and_provider_errors_sanitized():
    conn = FakeConn([("not-a-reply",)])
    source = EmpireDBFounderReplyMailbox(dsn="reader", connect_factory=lambda *a,**kw: conn)
    with pytest.raises(MailboxReadUnavailable, match="CANONICAL_REPLY_SCHEMA_MISMATCH"):
        source.list_received(limit=1)
    def fail(*args,**kwargs):
        raise RuntimeError("postgres-credential-is-secret")
    source = EmpireDBFounderReplyMailbox(dsn="reader", connect_factory=fail)
    with pytest.raises(MailboxReadUnavailable) as error:
        source.list_received(limit=1)
    assert "postgres-credential-is-secret" not in str(error.value)


def test_founder_router_canonical_mode_is_explicit_and_does_not_send(monkeypatch, tmp_path):
    monkeypatch.setenv("EMPIRE_FOUNDER_MAILBOX_PROVIDER", "empiredb_canonical_replies")
    monkeypatch.delenv("EMPIRE_FOUNDER_REPLY_READER_DSN", raising=False)
    app = FastAPI()
    app.include_router(create_founder_mailbox_router(identity_env_path=tmp_path / "absent.env"))
    client = TestClient(app)
    data = client.get("/v1/founder-mailbox/readiness").json()
    assert data["provider"] == "empiredb_canonical_replies"
    assert data["configured"] is False
    assert data["execution_authority"] == "none"
    assert "NOT_GENERAL_INBOX" in data["scope"]
    response = client.get("/v1/founder-mailbox/summary?limit=1")
    assert response.status_code == 503


def test_canonical_reply_and_sent_intent_share_one_thread_without_forged_email_headers():
    from empire_os.empire_mailbox import build_mailbox
    source = EmpireDBFounderReplyMailbox(dsn='fixture-reader')
    sent = source._sent(OUT_ROW)
    incoming = source._received(IN_ROW)
    mailbox = build_mailbox([sent], [incoming], provider='empiredb_canonical_replies', suppression_evidence_complete=False)
    assert mailbox['thread_count'] == 1
    assert mailbox['threads'][0]['intent_id'] == IID
    assert mailbox['threads'][0]['thread_id'] == IID
    assert mailbox['threads'][0]['event_count'] == 2
    assert mailbox['summary']['replies'] == 1
    assert mailbox['summary']['verified_canonical_buyer_replies'] == 0
    assert mailbox['canonical_buyer_conversation_verified'] is False
    assert mailbox['suppression_evidence_complete'] is False
    assert mailbox['threads'][0]['classification'] == 'unknown'
    assert mailbox['read_only'] is True


def test_unverified_provider_fields_cannot_self_claim_canonical_thread():
    from empire_os.empire_mailbox import normalise_received_email, normalise_sent_email
    assert normalise_received_email({'id':'provider-a', 'intent_id':IID, 'from':'buyer@example.org'}, provider='owned_imap')['intent_id'] is None
    assert normalise_sent_email({'id':'canonical-intent:not-a-uuid', 'canonical_intent_state_only':True}, provider='empiredb_canonical_replies')['intent_id'] is None
    assert normalise_received_email({'id':'canonical-reply:x', 'intent_id':'not-a-uuid'}, provider='empiredb_canonical_replies')['intent_id'] is None


def test_systemd_reader_credential_is_private_and_only_for_canonical_view(tmp_path, monkeypatch):
    from empire_os.empiredb_founder_reply_mailbox import SYSTEMD_CREDENTIAL
    secret = tmp_path / SYSTEMD_CREDENTIAL
    secret.write_text('postgresql://read-only@localhost/empiredb\n')
    secret.chmod(0o600)
    monkeypatch.setenv('CREDENTIALS_DIRECTORY', str(tmp_path))
    monkeypatch.delenv('EMPIRE_FOUNDER_REPLY_READER_DSN', raising=False)
    provider = EmpireDBFounderReplyMailbox()
    assert provider.configured is True
    assert provider.readiness()['execution_authority'] == 'none'
    secret.chmod(0o644)
    assert EmpireDBFounderReplyMailbox().configured is False
    secret.chmod(0o600)
    secret.write_text('postgresql://reader@example/db\nsecond-line')
    assert EmpireDBFounderReplyMailbox().configured is False
    secret.unlink()
    secret.symlink_to(tmp_path / 'other')
    assert EmpireDBFounderReplyMailbox().configured is False
