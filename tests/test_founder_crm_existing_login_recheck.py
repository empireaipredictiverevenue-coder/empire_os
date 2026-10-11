"""Post-redemption founder CRM login check never reuses invitation token."""
import importlib.util
from pathlib import Path

P=Path(__file__).resolve().parents[1]/"scripts/redeem_founder_crm_invitation_local.py"
spec=importlib.util.spec_from_file_location("first_party_crm_recheck",P)
module=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_existing_login_and_both_bounded_reads(monkeypatch,capsys):
    password="synthetic-test-password-NOT-PRODUCTION"
    monkeypatch.setattr(module.getpass,"getpass",lambda _:password)
    sent=[]
    def send(path,body):
        sent.append((path,body))
        return 200,{"access_token":"synthetic-bearer-never-print"}
    monkeypatch.setattr(module,"post",send)
    seen=[]
    monkeypatch.setattr(module,"get_authenticated",lambda path,bearer:
                        seen.append((path,bearer)) or 200)
    def no_invite():
        raise AssertionError("must never read or reuse invitation")
    monkeypatch.setattr(module,"invitation",no_invite)
    assert module.verify_existing_login()==0
    assert len(sent)==1
    assert sent[0][0]=="/v1/revenue-crm/auth/login"
    assert sent[0][1]["password"]==password
    assert len(seen)==2
    emitted=capsys.readouterr().out
    assert "CRM_FOUNDER_SETUP=FIRST_PARTY_LOGIN_VERIFIED" in emitted
    assert password not in emitted
    assert "synthetic-bearer" not in emitted
    assert "EI1_" not in emitted


def test_transient_prospect_failure_keeps_login_and_fails_closed(monkeypatch,capsys):
    monkeypatch.setattr(module.getpass,"getpass",lambda _:"synthetic-long-test-password")
    monkeypatch.setattr(module,"post",lambda *args:(200,{"access_token":"fake"}))
    monkeypatch.setattr(module,"get_authenticated",lambda path,bearer:
                        503 if path.endswith("/prospects") else 200)
    assert module.verify_existing_login()==4
    out=capsys.readouterr().out
    assert "CRM_FOUNDER_PROSPECT_HTTP=503" in out
    assert "CRM_FOUNDER_BUYER_HTTP=200" in out
    assert "AUTHENTICATED_READ_STILL_FAIL_CLOSED" in out


def test_login_wrong_password_without_invitation_retry(monkeypatch,capsys):
    monkeypatch.setattr(module.getpass,"getpass",lambda _:"synthetic-long-test-password")
    monkeypatch.setattr(module,"post",lambda *args:(401,{}))
    assert module.verify_existing_login()==4
    assert "LOGIN_NOT_VERIFIED" in capsys.readouterr().out


def test_first_login_mode_retained_and_login_only_gated():
    src=P.read_text()
    assert '--verify-existing-login' in src
    assert '--interactive-first-login' in src
    assert 'if sys.argv[1:]==["--verify-existing-login"]:' in src
    assert 'return verify_existing_login()' in src
    assert "sys.stdin.isatty()" in src
    assert "getpass.getpass" in src
    assert 'HTTPConnection("127.0.0.1",8783,timeout=12)' in src
    assert 'HTTPConnection("127.0.0.1",8783,timeout=8)' in src
    assert "print(bearer)" not in src
    assert "print(password)" not in src
