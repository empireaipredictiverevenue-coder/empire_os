"""Founder Workspace read consent may not replace OAuth from the wrong account."""
from __future__ import annotations

import json
import sys

import pytest

from scripts import authorize_empire_gmail as authorization
from empire_os.google_workspace_mailbox import SCOPES


class FakeCredentials:
    def __init__(self, scopes):
        self.scopes = scopes

    def to_json(self):
        return json.dumps({"scopes": self.scopes, "refresh_token": "fixture-secret"})


class FakeFlow:
    scopes_seen = None
    creds = None

    @classmethod
    def from_client_secrets_file(cls, path, scopes):
        cls.scopes_seen = scopes
        return cls()

    def run_local_server(self, **kwargs):
        return self.creds


class ProfileService:
    def __init__(self, email):
        self.email = email

    def users(self):
        return self

    def getProfile(self, **kwargs):
        return self

    def execute(self):
        return {"emailAddress": self.email}


def setup(monkeypatch, tmp_path):
    client = tmp_path / "oauth_client.json"
    token = tmp_path / "oauth_token.json"
    client.write_text("{}")
    token.write_text("ORIGINAL_TOKEN_NOT_REPLACED")
    monkeypatch.setattr(authorization.InstalledAppFlow, "from_client_secrets_file",
                        FakeFlow.from_client_secrets_file)
    monkeypatch.setattr(sys, "argv", ["authorize_empire_gmail.py",
        "--client", str(client), "--token", str(token), "--mailbox-read"])
    FakeFlow.creds = FakeCredentials(SCOPES)
    return token


def test_mismatched_workspace_account_cannot_replace_working_send_token(monkeypatch, tmp_path):
    token = setup(monkeypatch, tmp_path)
    monkeypatch.setattr(authorization, "build_gmail_service", lambda _: ProfileService("flavag83@gmail.com"))
    with pytest.raises(SystemExit, match="WORKSPACE_MAILBOX_ACCOUNT_MISMATCH"):
        authorization.main()
    assert token.read_text() == "ORIGINAL_TOKEN_NOT_REPLACED"
    assert FakeFlow.scopes_seen == SCOPES


def test_explicit_read_consent_scopes_required_before_token_replacement(monkeypatch, tmp_path):
    token = setup(monkeypatch, tmp_path)
    FakeFlow.creds = FakeCredentials([SCOPES[0]])
    monkeypatch.setattr(authorization, "build_gmail_service", lambda _: ProfileService("phil@mail.empire-ai.co.uk"))
    with pytest.raises(SystemExit, match="WORKSPACE_MAILBOX_SCOPES_NOT_GRANTED"):
        authorization.main()
    assert token.read_text() == "ORIGINAL_TOKEN_NOT_REPLACED"


def test_verified_workspace_account_can_replace_token_only_with_explicit_consent(monkeypatch, tmp_path):
    token = setup(monkeypatch, tmp_path)
    monkeypatch.setattr(authorization, "build_gmail_service", lambda _: ProfileService("phil@mail.empire-ai.co.uk"))
    assert authorization.main() == 0
    assert json.loads(token.read_text())["scopes"] == SCOPES
    assert oct(token.stat().st_mode & 0o777) == "0o600"
