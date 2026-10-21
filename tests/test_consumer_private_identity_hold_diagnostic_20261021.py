"""Stage-only hold diagnostics: no SQL errors, passwords, or PII printed."""
from __future__ import annotations
import json
from types import SimpleNamespace

import pytest
from scripts import diagnose_consumer_private_identity_hold_20261021 as probe

SECRET = "d"*64


def _approved_stub(*, broken_vault=False):
    if broken_vault:
        def fail():
            raise OSError("synthetic_error "+SECRET)
    else:
        def fail():
            return (SECRET,{})
    return SimpleNamespace(read_custody=fail)


def test_root_required_and_no_secret_load(monkeypatch):
    monkeypatch.setattr(probe.os,"geteuid",lambda:1000)
    result=probe.diagnosed_readonly(original=_approved_stub())
    assert result["status"].endswith("_HOLD")
    assert result["first_failing_stage"]=="IDENTITY_SOURCE"


def test_vault_error_redacted(monkeypatch):
    monkeypatch.setattr(probe.os,"geteuid",lambda:0)
    result=probe.diagnosed_readonly(original=_approved_stub(broken_vault=True))
    assert result["first_failing_stage"]=="VAULT"
    assert SECRET not in json.dumps(result)
    assert "synthetic_error" not in json.dumps(result)


def test_scram_login_error_redacted(monkeypatch):
    monkeypatch.setattr(probe.os,"geteuid",lambda:0)
    original=SimpleNamespace(DB="empiredb",LOGIN="empire_consumer_optin_login",
                             read_custody=lambda:(SECRET,{}))
    def no_connect(**kwargs):
        assert kwargs["password"]==SECRET
        raise RuntimeError("FATAL synthetic connection rejected "+SECRET)
    result=probe.diagnosed_readonly(original=original,connect=no_connect)
    assert result["first_failing_stage"]=="SCRAM_CONNECT"
    assert SECRET not in json.dumps(result)
    assert "FATAL" not in json.dumps(result)


@pytest.mark.parametrize(("fail_at","stage"),[
    (1,"READ_ONLY_TX"),(2,"LOGIN_IDENTITY"),
    (3,"ROLE_ATTRIBUTES"),(4,"MEMBERSHIP"),
    (5,"SET_LOCAL_ROLE"),(6,"WRITER_IDENTITY"),
    (7,"RLS_SCHEMA"),(8,"POLICY_SET"),
    (9,"TABLE_ACL"),(10,"RLS_ZERO_ROW_ACCESS"),
])
def test_sql_failures_emit_only_stage(monkeypatch,fail_at,stage):
    monkeypatch.setattr(probe.os,"geteuid",lambda:0)
    original=SimpleNamespace(
        DB="empiredb",LOGIN="empire_consumer_optin_login",
        WRITER="empire_consumer_optin_writer",
        TABLES=("a","b","c","d","e"),
        POLICIES=("pa","pb","pc","pd","pe"),
        read_custody=lambda:(SECRET,{}),
    )
    class Conn:
        n=0
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def execute(self,sql,params=()):
            self.n+=1
            if self.n==fail_at:
                raise RuntimeError("private_error "+SECRET)
            if self.n in (2,6):
                row=(original.LOGIN,
                     original.LOGIN if self.n==2 else original.WRITER,
                     original.DB,"on")
            elif self.n==3:
                row=(True,)*12
            elif self.n==4:
                row=(1,True)
            elif self.n==7:
                row=(5,)
            elif self.n>=9:
                row=(True,)*4
            else:
                row=None
            return SimpleNamespace(
                fetchone=lambda:row,
                fetchall=lambda:[(p,) for p in original.POLICIES],
            )
        def rollback(self):pass
    result=probe.diagnosed_readonly(original=original,connect=lambda **kwargs: Conn())
    assert result["status"]=="CONSUMER_PRIVATE_IDENTITY_DIAGNOSTIC_HOLD"
    assert result["first_failing_stage"]==stage
    assert SECRET not in json.dumps(result)


def test_no_create_mail_or_plaintext_in_documented_probe():
    from pathlib import Path
    src=Path(probe.__file__).read_text()
    assert "SET TRANSACTION READ ONLY" in src
    assert "LIMIT 0" in src
    assert "--apply" not in src
    assert "CREATE ROLE" not in src
    assert "INSERT INTO" not in src
    assert "send_verification" not in src
    assert "ROOT_SOURCE_SHA256" in src
