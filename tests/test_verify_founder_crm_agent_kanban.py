"""Synthetic, secret-safe verification of interactive founder CRM Kanban."""
from __future__ import annotations

import json

import pytest

from scripts import verify_founder_crm_agent_kanban as canary

LANES = canary.LANES


def board():
    return {
        "schema_version": "empire.departments.kanban.v1",
        "source": "canonical_department_work_queue",
        "tenant_scope": "explicit_tenant",
        "read_only": True,
        "execution_authority": "none",
        "lanes": {lane: {"total": 0, "cards": [], "truncated": False} for lane in LANES},
    }


def synthetic_session(monkeypatch, *, bearer="synthetic_do_not_print",
                      normal=None, spoof=None, login_status=200):
    monkeypatch.setattr(canary.getpass, "getpass", lambda _: "x" * 18)
    monkeypatch.setattr(canary, "post", lambda path, payload: (
        login_status, {"access_token": bearer} if login_status == 200 else {},
    ))
    def response(*, token=None, spoof=False):
        if token is None:
            return 401, None
        return (200, (spoof if isinstance(spoof, dict) else normal))
    def result(*, token=None, spoof=False):
        if token is None:
            return 401, None
        return 200, (globals()["board"]() if normal is None else (
            spoofed if spoof else normal
        ))
    spoofed = globals()["board"]() if spoof is None else spoof
    monkeypatch.setattr(canary, "_read_board", result)


def test_success_statuses_and_totals_without_credentials_leaked(monkeypatch, capsys):
    synthetic_session(monkeypatch)
    assert canary.verify_authenticated_board() == 0
    output = capsys.readouterr().out
    assert "KANBAN_AUTHENTICATED_HTTP=200" in output
    assert "KANBAN_ANONYMOUS_HTTP=401" in output
    assert "KANBAN_FORGED_TENANT_HTTP=401" in output
    assert "KANBAN_CANARY=EXISTING_FOUNDER_TENANT_READ_VERIFIED" in output
    assert "synthetic_do_not_print" not in output
    assert "@" not in output
    assert "00000000-0000" not in output


def test_invalid_password_denies_without_login(monkeypatch):
    monkeypatch.setattr(canary.getpass, "getpass", lambda _: "x")
    monkeypatch.setattr(canary, "_read_board", lambda **kw: (401, None))
    monkeypatch.setattr(canary, "post", lambda *_: (_ for _ in ()).throw(
        AssertionError("login attempted despite invalid password")
    ))
    assert canary.verify_authenticated_board() == 2


def test_synthetic_failed_authentication_cannot_read_board(monkeypatch):
    calls = []
    monkeypatch.setattr(canary.getpass, "getpass", lambda _: "x" * 16)
    monkeypatch.setattr(canary, "post", lambda *_: (401, {}))
    def request(*, token=None, spoof=False):
        calls.append((token, spoof))
        return 401, None
    monkeypatch.setattr(canary, "_read_board", request)
    assert canary.verify_authenticated_board() == 4
    assert all(token is None for token, _ in calls)


def test_spoofed_tenant_must_not_change_canonical_board(monkeypatch, capsys):
    normal = board()
    different = board()
    different["lanes"]["ready"]["total"] = 1
    different["lanes"]["ready"]["cards"] = [
        {"work_id": "unexpected"}]
    synthetic_session(monkeypatch, normal=normal, spoof=different)
    assert canary.verify_authenticated_board() == 4
    assert "SCOPE_MISMATCH" in capsys.readouterr().out


def test_untrusted_card_contents_are_not_accepted():
    invalid = board()
    invalid["lanes"]["ready"]["total"] = 1
    invalid["lanes"]["ready"]["cards"] = [{
        "work_id": "other_tenant_secret", "intelligence_request": "sensitive",
    }]
    with pytest.raises(ValueError, match="unapproved_canonical_card_field"):
        canary._validate_board(invalid)


@pytest.mark.parametrize("change", [
    {"execution_authority": "internal_write"},
    {"tenant_scope": "unbound"},
    {"read_only": False},
    {"source": "untrusted_shadow_queue"},
])
def test_invalid_scope_and_authority_denied(change):
    invalid = board()
    invalid.update(change)
    with pytest.raises(ValueError, match="contract_mismatch"):
        canary._validate_board(invalid)


def test_no_tty_or_impersonated_linux_owner_blocks_before_login(monkeypatch):
    monkeypatch.setattr(canary.sys, "argv", ["canary", "--interactive-founder-read-only"])
    monkeypatch.setattr(canary.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(canary, "verify_authenticated_board", lambda: (_ for _ in ()).throw(
        AssertionError("cannot prompt for password without TTY")
    ))
    assert canary.main() == 3


def test_static_script_does_not_log_bearer_or_password():
    source = canary.__file__
    text = open(source, encoding="utf-8").read()
    assert "getpass.getpass" in text
    assert 'credentials.clear()' in text
    assert 'token = ""' in text
    assert 'password = ""' in text
    assert "os.geteuid()" in text
    assert "print(token)" not in text
    assert "print(password)" not in text
