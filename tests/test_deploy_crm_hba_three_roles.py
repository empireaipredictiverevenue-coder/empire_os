"""Prove fail-closed, exact-role HBA patch without touching production."""
from __future__ import annotations
import importlib.util
from pathlib import Path

import pytest

P=Path(__file__).resolve().parents[1]/"scripts/deploy_crm_hba_three_roles.py"
spec=importlib.util.spec_from_file_location("crm_hba",P)
module=importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


def test_exact_three_additive_rules_and_byte_for_byte_original():
    original=(b"# Default pg_hba.conf\n"
              b"local all postgres peer\n"
              b"local all all peer\n"
              b"host all all 127.0.0.1/32 scram-sha-256\n")
    patched=module.amended(original)
    assert patched.endswith(original)
    assert patched.startswith(b"# BEGIN EMPIRE_CRM_FOUNDER_THREE_LOGINS_V1\n")
    assert patched.count(b"local   empiredb") == 3
    for role in ("empire_crm_auth_login","empire_crm_membership_login",
                 "empire_crm_tenant_708efd4b53b2"):
        assert patched.count(role.encode())==1
    assert b"local all all peer" in patched
    assert b"host all all 127.0.0.1/32 scram-sha-256" in patched
    assert b"trust" not in patched
    assert b"0.0.0.0" not in patched

def test_idempotence_fail_closed_no_broadening():
    original=b"local all all peer\n"
    with pytest.raises(ValueError,match="already patched"):
        module.amended(module.amended(original))
    for source in (b"",b" ",b"local all all peer\r\n",b"local all all peer\x00\n"):
        with pytest.raises(ValueError):
            module.amended(source)

def test_production_cli_has_hard_separate_approval_and_no_role_or_send():
    data=P.read_text()
    assert "--approved-exact-three-crm-hba-rules" in data
    assert "os.geteuid() != 0" in data
    assert "fcntl.flock" in data
    assert 'f"safe.directory={ROOT}"' in data  # checked-in source readback only
    assert "git checkout" not in data and "git reset" not in data
    assert "git stash" not in data
    assert "pg_hba.conf.before" in data
    assert "sha256" in data
    assert "pg_reload_conf()" in data
    assert "post-reload auth policy not verified" in data
    assert "ROLLBACK=ORIGINAL_FILE_RESTORED" in data
    assert "CONCURRENT_CHANGE" in data.upper()
    assert "ALTER ROLE" not in data
    assert "CREATE ROLE" not in data
    assert "DROP ROLE" not in data
    assert "GRANT " not in data
    assert "CREATE TABLE" not in data
    assert "systemctl restart" not in data
    assert "empire_crm_login_credentials" not in data
    assert "auth_method" not in data # policy evaluated by canonical probe

def test_nonroot_or_unapproved_does_not_touch_files(monkeypatch,capsys):
    monkeypatch.setattr(module.os,"geteuid",lambda:1000)
    assert module.main()==3
    assert "BLOCKED_EXACT_FLAGS_REQUIRED" in capsys.readouterr().out
    monkeypatch.setattr(module.sys,"argv",["script","--apply","--approved-exact-three-crm-hba-rules"])
    assert module.main()==3
    assert "BLOCKED_ROOT_OPERATOR_REQUIRED" in capsys.readouterr().out

def test_cluster_guard_uses_postgresql_concat_boolean_text_not_psql_short_display(monkeypatch):
    # pg_is_in_recovery() displays 'f' in a boolean column, but is rendered
    # 'false' when concatenated with text in production's cluster identity.
    from types import SimpleNamespace
    monkeypatch.setattr(module.subprocess,"run", lambda *a, **kw: SimpleNamespace(returncode=0))
    good=f"empiredb|{module.DATA}|{module.HBA}|false"
    monkeypatch.setattr(module,"invoke_psql",lambda **kw:good)
    module.cluster_guard()
    for wrong in (good[:-5]+"f",good[:-5]+"true", "otherdb|"+good.split("|",1)[1],
                  f"empiredb|/tmp/other|{module.HBA}|false"):
        monkeypatch.setattr(module,"invoke_psql",lambda **kw:wrong)
        with pytest.raises(RuntimeError,match="noncanonical PostgreSQL cluster"):
            module.cluster_guard()
