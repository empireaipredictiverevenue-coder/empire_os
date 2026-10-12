"""Operator provisioning is two distinct exact opt-in paths, never implicit."""
from __future__ import annotations

import json
from pathlib import Path
import re

import pytest

from scripts import provision_bsc_financial_operator_logins as provisioning
from scripts import prepare_bsc_operator_hba as hba
from empire_os.bsc_payment_operator_readiness import (
    EXPECTED, LOGIN_ROLES, LOGIN_FLAGS, MANDATORY_FUNCTIONS,
)


def test_financial_sql_identities_are_distinct_from_legacy_app_and_each_other():
    assert len(EXPECTED)==2
    assert len(set(EXPECTED.values()))==2
    assert "empiredb_app_login" not in EXPECTED.values()
    assert "empire_payment_approver" not in EXPECTED.values()
    assert "empire_escrow_verifier" not in EXPECTED.values()
    assert LOGIN_FLAGS==(True,False,False,False,False,False,False)


def test_actual_role_write_path_has_exact_pair_and_noninherited_set_option():
    import inspect
    text=inspect.getsource(provisioning._internal_apply)
    assert "CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB" in text
    assert "NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}" in text
    assert "GRANT {} TO {} WITH INHERIT FALSE, SET TRUE, ADMIN FALSE" in text
    assert "psycopg" in text
    assert "cur.execute" in text
    assert "GRANT ALL" not in text
    assert "ALTER DEFAULT PRIVILEGES" not in text
    assert "PUBLIC" not in text


def test_random_credentials_are_unique_strong_and_not_fixed_source_strings():
    a=provisioning.safe_password_pair()
    b=provisioning.safe_password_pair()
    assert set(a)==set(LOGIN_ROLES)
    assert set(b)==set(LOGIN_ROLES)
    assert len(set(a.values()))==2
    assert all(len(value)>=48 for value in a.values())
    assert a!=b


def test_operator_vault_has_root_private_split_files_only(tmp_path,monkeypatch):
    vault=tmp_path/"private-bsc-operators"
    monkeypatch.setattr(provisioning,"VAULT",vault)
    passwords=provisioning.safe_password_pair()
    provisioning._store_credentials(passwords)
    assert vault.stat().st_mode & 0o777==0o700
    assert {p.name for p in vault.iterdir()}=={name+".pgpass" for name in LOGIN_ROLES}
    for role in LOGIN_ROLES:
        p=vault/(role+".pgpass")
        assert p.stat().st_mode & 0o777==0o600
        data=p.read_text()
        assert data.startswith("/var/run/postgresql:5432:empiredb:"+role+":")
        assert data.endswith(passwords[role]+"\n")
        other=next(login for login in LOGIN_ROLES if login!=role)
        assert passwords[other] not in data
    with pytest.raises(RuntimeError,match="credential vault not overwritten"):
        provisioning._store_credentials(passwords)


def test_hba_apply_and_role_apply_have_separate_explicit_approval_strings():
    import inspect
    src=inspect.getsource(hba.main)
    login_src=inspect.getsource(provisioning._root_main)
    assert '"--approved-exact-two-bsc-financial-hba-rules"' in src
    assert '"--approved-two-bsc-financial-operator-logins"' in login_src
    assert "prior.reload()" in src
    assert "financial" in src
    assert "grant" not in src.lower() or "roles" in src.lower()
    assert "_source_guard()" in login_src


def test_role_provisioning_invocation_missing_approval_does_not_call_privileged_code(monkeypatch,capsys):
    monkeypatch.setattr(provisioning.os,"geteuid",lambda:0)
    monkeypatch.setattr(provisioning,"_postgres_child",
                        lambda *a,**kw:pytest.fail("PG_OR_ROLES_MUTATED"))
    assert provisioning._root_main(["--apply"])==3
    assert provisioning._root_main(["--approved-two-bsc-financial-operator-logins"])==3
    assert provisioning._root_main([])==3
    assert "EXACT_FOUNDER_APPROVAL" in capsys.readouterr().out


def test_hba_cannot_apply_without_exact_flag_and_root(monkeypatch):
    import sys
    monkeypatch.setattr(hba.sys,"argv",["operator","--apply"])
    assert hba.main()==3
    monkeypatch.setattr(hba.sys,"argv",["operator","--preflight"])
    monkeypatch.setattr(hba.os,"geteuid",lambda:1000)
    assert hba.main()==3


def test_db_login_provisioner_rejects_untrusted_internal_command_and_non_postgres():
    # CLI's exact internal command is postgres-only; the human can never
    # supply arbitrary SQL, roles, or passwords on the command line.
    import inspect
    src=inspect.getsource(provisioning.main)
    assert 'pwd.getpwnam("postgres").pw_uid' in src
    assert "--internal-apply" in src
    assert "json.load(sys.stdin)" in src


def test_private_vault_is_outside_repo_and_service_configuration():
    assert str(provisioning.VAULT).startswith("/var/lib/empire")
    assert not str(provisioning.VAULT).startswith("/srv/empire_os")
    assert str(provisioning.BACKUPS).startswith("/var/backups/empiredb")
    assert str(provisioning.LOCK).startswith("/run/lock")
    assert provisioning.DB == "empiredb"
    assert all("escrow" in n or "payment" in n for n in LOGIN_ROLES)


def test_preflight_is_readonly_and_never_performs_financial_role_grants(monkeypatch,capsys,tmp_path):
    monkeypatch.setattr(provisioning.os,"geteuid",lambda:0)
    monkeypatch.setattr(provisioning,"LOCK",tmp_path/"lock")
    monkeypatch.setattr(provisioning,"VAULT",tmp_path/"absent-vault")
    monkeypatch.setattr(provisioning.hba_operator.prior,"cluster_guard",lambda:None)
    expected={"status":"READY_FOR_SEPARATELY_APPROVED_TWO_LOGIN_PROVISIONING",
              "roles_created":0,"database_mutations":0}
    monkeypatch.setattr(provisioning,"_postgres_child",lambda *a,**kw:expected)
    monkeypatch.setattr(provisioning,"_store_credentials",lambda *a,**kw:
                        pytest.fail("CREDENTIALS_WRITTEN_ON_PREFLIGHT"))
    monkeypatch.setattr(provisioning,"_backup_global_roles",lambda:
                        pytest.fail("DB_GLOBALS_BACKED_UP_ON_PREFLIGHT"))
    assert provisioning._root_main(["--preflight"])==0
    out=capsys.readouterr().out
    assert "READY_FOR_SEPARATE_EXACT_FOUNDER_APPROVAL" in out
    assert "password" not in out.lower()


@pytest.mark.parametrize("status",[
    "PREPARE_EXACT_TWO_LOCAL_SCRAM_HBA_RULES",
    "BLOCKED_DB_AUTHORITY_OR_ROLE_INVARIANT",
    "BLOCKED_PREEXISTING_OPERATOR_CREDENTIAL_VAULT",
])
def test_login_provisioner_holds_when_hba_or_security_not_ready(monkeypatch,capsys,tmp_path,status):
    monkeypatch.setattr(provisioning.os,"geteuid",lambda:0)
    monkeypatch.setattr(provisioning,"LOCK",tmp_path/"lock")
    monkeypatch.setattr(provisioning,"VAULT",tmp_path/"absent-vault")
    monkeypatch.setattr(provisioning.hba_operator.prior,"cluster_guard",lambda:None)
    monkeypatch.setattr(provisioning,"_postgres_child",lambda *a,**kw:{"status":status})
    monkeypatch.setattr(provisioning,"_backup_global_roles",lambda:
                        pytest.fail("UNSAFE_PROVISIONING_STARTED"))
    assert provisioning._root_main(["--apply",
        "--approved-two-bsc-financial-operator-logins"])==2
    assert "HELD_CATALOG_OR_HBA_UNREADY" in capsys.readouterr().out


def test_passwords_are_not_in_process_arguments_or_normal_stdout():
    import inspect
    src=inspect.getsource(provisioning._postgres_child)
    assert 'input=None if payload is None else json.dumps(payload,sort_keys=True)' in src
    assert 'capture_output=True' in src
    assert 'print(' not in src
    src=inspect.getsource(provisioning._root_main)
    assert 'print(password' not in src
    assert 'print(derived' not in src


def test_additive_hba_rejects_duplicate_role_and_preserves_original_tail():
    original=b"local empiredb empire_crm_auth_login scram-sha-256\nlocal all all peer\n"
    patched=hba.additive_hba_patch(original)
    assert patched.endswith(original)
    assert patched.count(b"empire_payment_approver_login")==1
    assert patched.count(b"empire_escrow_verifier_login")==1
    with pytest.raises(ValueError):
        hba.additive_hba_patch(patched)
