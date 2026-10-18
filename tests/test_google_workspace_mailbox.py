"""Bounded Google Workspace inbox reuse; no new mail runtime or send path."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.google_workspace_mailbox import (
    GoogleWorkspaceMailboxProvider, MailboxReadUnavailable, SCOPES,
)
from empire_os.empire_mailbox import normalise_received_email, normalise_sent_email
from empire_os.founder_mailbox_api import create_founder_mailbox_router


class FakeAPI:
    def __init__(self, email="phil@empire-ai.co.uk"):
        self.email = email
        self.operation = None
        self.calls = []

    def users(self):
        return self

    def getProfile(self, **kwargs):
        self.calls.append(("profile", kwargs))
        self.operation = "profile"
        return self

    def messages(self):
        return self

    def list(self, **kwargs):
        self.calls.append(("list", kwargs))
        self.operation = "list"
        return self

    def get(self, **kwargs):
        self.calls.append(("get", kwargs))
        self.operation = "get"
        return self

    def execute(self):
        if self.operation == "profile":
            return {"emailAddress": self.email}
        if self.operation == "list":
            return {"messages": [{"id": "abcdef1234567890"}]}
        if self.operation == "get":
            return {"id": "abcdef1234567890", "labelIds": ["INBOX", "UNREAD"],
                    "internalDate": "1791950000000", "snippet": "Thanks for connecting",
                    "payload": {"headers": [
                        {"name": "From", "value": "A Person <person@example.org>"},
                        {"name": "To", "value": "Phil <phil@mail.empire-ai.co.uk>"},
                        {"name": "Subject", "value": "Re: Hello"},
                        {"name": "Message-ID", "value": "<untrusted@example.org>"},
                    ]}}
        raise AssertionError("unexpected operation")


def token_file(tmp_path: Path, scopes):
    path = tmp_path / "token.json"
    path.write_text(json.dumps({"refresh_token": "private-stub", "scopes": scopes}))
    path.chmod(0o600)
    return path


def test_old_send_only_token_cannot_read_inbox(tmp_path):
    path = token_file(tmp_path, [SCOPES[0]])
    provider = GoogleWorkspaceMailboxProvider(token_path=path)
    assert provider.configured is False
    assert provider.readiness()["configured"] is False
    with pytest.raises(MailboxReadUnavailable, match="WORKSPACE_READ_SCOPE_NOT_AUTHORIZED"):
        provider.list_received(limit=1)


def test_scoped_token_can_be_configured_but_not_assumed_authentic(tmp_path):
    path = token_file(tmp_path, SCOPES)
    provider = GoogleWorkspaceMailboxProvider(token_path=path)
    assert provider.configured is True
    assert provider.readiness()["canonical_identity_verified"] is False
    assert provider.suppression_evidence_complete is False
    assert provider.list_suppressions(limit=5) == []


def test_authenticates_exact_workspace_account_before_read(tmp_path, monkeypatch):
    token = token_file(tmp_path, SCOPES)
    class FakeCreds:
        expired = False
        valid = True
        refresh_token = "private"
    from google.oauth2.credentials import Credentials
    monkeypatch.setattr(Credentials, "from_authorized_user_file", staticmethod(lambda *args, **kwargs: FakeCreds()))
    good = FakeAPI()
    provider = GoogleWorkspaceMailboxProvider(token_path=token, service_factory=lambda creds: good)
    rows = provider.list_received(limit=1)
    assert len(rows) == 1
    assert rows[0]["provider"] == "google_workspace"
    assert rows[0]["body_preview_only"] is True
    assert rows[0]["source_received_at_verified"] is False
    assert rows[0]["canonical_contact_identity_verified"] is False
    assert rows[0]["id"] == "workspace:inbox:abcdef1234567890"
    assert good.calls[0] == ("profile", {"userId": "me"})
    assert good.calls[1][0] == "list"
    assert good.calls[1][1]["labelIds"] == ["INBOX"]
    assert good.calls[1][1]["maxResults"] == 1
    assert good.calls[2][1]["format"] == "metadata"
    assert "raw" not in str(good.calls).lower()
    wrong = FakeAPI(email="flavag83@gmail.com")
    incorrect = GoogleWorkspaceMailboxProvider(token_path=token, service_factory=lambda creds: wrong)
    with pytest.raises(MailboxReadUnavailable, match="WORKSPACE_ACCOUNT_IDENTITY_MISMATCH"):
        incorrect.list_received(limit=1)
    assert wrong.calls == [("profile", {"userId": "me"})]


def test_invalid_mailbox_id_or_gmail_label_is_held(tmp_path):
    provider = GoogleWorkspaceMailboxProvider(token_path=token_file(tmp_path, SCOPES))
    provider._service = lambda: FakeAPI()
    with pytest.raises(MailboxReadUnavailable, match="WORKSPACE_MESSAGE_ID_MISMATCH"):
        provider.get_received("workspace:sent:abcdef1234567890")
    with pytest.raises(MailboxReadUnavailable, match="WORKSPACE_INVALID_BOUNDED_READ"):
        provider._read("inbox", limit=999)
    with pytest.raises(MailboxReadUnavailable, match="WORKSPACE_UNEXPECTED_MAILBOX_LABEL"):
        provider._row({"id": "abcdef1234567890", "labelIds": ["SENT"]}, role="inbox")


def test_provider_only_messages_do_not_promote_canonical_message_id():
    row = {"id": "workspace:sent:abcdef1234567890",
           "message_id": "<uncorroborated@example.org>",
           "to": ["contact@example.org"], "subject": "Hi", "status": "sent"}
    sent = normalise_sent_email(row, provider="google_workspace")
    assert sent["message_id"] is None
    received = normalise_received_email(dict(row, text="Hello"), provider="google_workspace")
    assert received["message_id"] is None


def test_router_requires_explicit_workspace_mode_and_retains_no_send(tmp_path, monkeypatch):
    monkeypatch.setenv("EMPIRE_FOUNDER_MAILBOX_PROVIDER", "google_workspace")
    monkeypatch.setattr(GoogleWorkspaceMailboxProvider, "configured", property(lambda self: False))
    app = FastAPI()
    app.include_router(create_founder_mailbox_router(identity_env_path=tmp_path / "missing.env"))
    response = TestClient(app).get("/v1/founder-mailbox/readiness")
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "google_workspace"
    assert payload["configured"] is False
    assert payload["status"] == "NOT_CONFIGURED"
    assert payload["execution_authority"] == "none"
    monkeypatch.setenv("EMPIRE_FOUNDER_MAILBOX_PROVIDER", "resend")
    with pytest.raises(RuntimeError, match="FOUNDER_MAILBOX_PROVIDER_NOT_AUTHORIZED"):
        create_founder_mailbox_router()
