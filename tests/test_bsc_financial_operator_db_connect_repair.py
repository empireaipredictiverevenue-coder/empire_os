"""BSC financial operators: exact two-LOGIN DB CONNECT repair, no funds."""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from empire_os.bsc_payment_operator_readiness import LOGIN_ROLES
from scripts import repair_bsc_financial_operator_db_connect as repair

MISSING={
    "status":repair.REQUIRES_GRANTS,
    "operator_db_connect_grant_count":0,
    "two_exact_local_scram_rules_effective":True,
    "exact_existing_nologin_permission_roles_safe":True,
    "exact_noninherited_set_role_memberships":True,
}
READY={**MISSING,"status":repair.CATALOG_READY,"operator_db_connect_grant_count":2}


def test_repair_internal_sql_contains_only_two_exact_connect_grants_not_money():
    body=inspect.getsource(repair._internal_grant)
    assert 'GRANT CONNECT ON DATABASE {} TO {}' in body
    assert 'for login in LOGIN_ROLES' in body
    assert 'conn,conn.cursor()' in body
    assert 'REQUIRES_GRANTS' in body
    assert 'has_function_privilege' not in body
    for forbidden in ("GRANT ALL", "GRANT CREATE", "GRANT TEMP",
                      "GRANT USAGE", "CREATE ROLE", "ALTER ROLE",
                      "approve_bsc_payment_request", "record_bsc_escrow_lifecycle",
                      "INSERT", "UPDATE ", "DELETE FROM", "eth_send"):
        assert forbidden not in body
    assert len(LOGIN_ROLES)==2


def test_repair_requires_exact_founder_authorisation_flag(monkeypatch,capsys):
    monkeypatch.setattr(repair.os,"geteuid",lambda:0)
    monkeypatch.setattr(repair,"_postgres_child",
                        lambda *args:pytest.fail("NO_PRIVILEGED_CHECK_WITH_BAD_FLAGS"))
    for args in ([],["--apply"],["--approved-exact-two-bsc-db-connect-grants"],
                 ["--apply","--wrong-approval"],["--apply","--approved-exact-two-bsc-db-connect-grants","--extra"]):
        assert repair._root_main(args)==3
    assert "HELD_EXACT_APPROVAL_FLAG_REQUIRED" in capsys.readouterr().out


def _preflight(monkeypatch,tmp_path,catalog):
    monkeypatch.setattr(repair.os,"geteuid",lambda:0)
    monkeypatch.setattr(repair,"LOCK",tmp_path/"read-only.lock")
    monkeypatch.setattr(repair.existing.hba_operator.prior,"cluster_guard",lambda:None)
    monkeypatch.setattr(repair,"_postgres_child",lambda op:
                        catalog if op=="--internal-catalog" else
                        pytest.fail("PRIVILEGED_WRITE_ON_READONLY_PREFLIGHT"))
    monkeypatch.setattr(repair,"_ensure_vault_safe",lambda:True)
    monkeypatch.setattr(repair,"_backup_acl",
                        lambda:pytest.fail("BACKUP_OR_WRITE_ON_READONLY_PREFLIGHT"))


def test_no_write_preflight_identifies_exact_missing_grants(monkeypatch,tmp_path,capsys):
    _preflight(monkeypatch,tmp_path,MISSING)
    assert repair._root_main(["--preflight"])==0
    out=capsys.readouterr().out
    assert "READY_FOR_EXACT_TWO_CONNECT_GRANT_APPROVAL" in out
    assert "checkout_payment_activation" in out
    assert "READ_ONLY" in out


@pytest.mark.parametrize("catalog",[
    {"status":"BLOCKED_PARTIAL_DATABASE_CONNECT_GRANTS","operator_db_connect_grant_count":1},
    {"status":"BLOCKED_UNSAFE_DATABASE_CREATE_OR_TEMP_GRANT","operator_db_connect_grant_count":0},
    {"status":"BLOCKED_UNEXPECTED_FINANCIAL_ROLE_MEMBERSHIP","operator_db_connect_grant_count":0},
])
def test_partial_or_excessive_grants_block_even_with_apply_approval(monkeypatch,tmp_path,capsys,catalog):
    config={**MISSING,**catalog}
    _preflight(monkeypatch,tmp_path,config)
    assert repair._root_main(["--apply","--approved-exact-two-bsc-db-connect-grants"])==2
    assert "HELD_UNSAFE_PARTIAL_OR_AUTHORITY_DRIFT" in capsys.readouterr().out


def test_preexisting_both_grants_is_safe_idempotent_without_new_sql(monkeypatch,tmp_path,capsys):
    _preflight(monkeypatch,tmp_path,READY)
    assert repair._root_main(["--preflight"])==0
    assert repair._root_main(["--apply","--approved-exact-two-bsc-db-connect-grants"])==0
    assert "ALREADY_GRANTED_NO_SQL_CHANGE" in capsys.readouterr().out


def test_operator_vault_missing_is_not_worked_around(monkeypatch,tmp_path,capsys):
    _preflight(monkeypatch,tmp_path,MISSING)
    monkeypatch.setattr(repair,"_ensure_vault_safe",lambda:False)
    assert repair._root_main(["--preflight"])==2
    assert "HELD_OPERATOR_VAULT_UNVERIFIED" in capsys.readouterr().out


def test_root_operator_source_and_postgres_child_are_scoped():
    c=inspect.getsource(repair._postgres_child)
    assert '"-m","scripts.repair_bsc_financial_operator_db_connect",operation' in c
    assert '"PGHOST": existing.SOCKET' in c
    assert '"PGPORT": "5432"' in c
    assert '"PGDATABASE": DB' in c
    assert "capture_output=True" in c
    root=inspect.getsource(repair._root_main)
    assert "_source_guard()" in root
    assert "_backup_acl()" in root
    assert '["--apply","--approved-exact-two-bsc-db-connect-grants"]' in root
    assert "_verify_two_password_logins()" in root


def test_private_operator_passfiles_never_logged_in_output(monkeypatch,tmp_path,capsys):
    _preflight(monkeypatch,tmp_path,MISSING)
    assert repair._root_main(["--preflight"])==0
    txt=capsys.readouterr().out.lower()
    for secret_key in ("password", "pgpass", "scram-sha-256$", "token", "secret"):
        assert secret_key not in txt


def test_all_incomplete_catalog_evidence_fails_closed(monkeypatch,tmp_path):
    data={**MISSING}
    data["status"]="BLOCKED_DATABASE_PRIVILEGE_CATALOG_UNAVAILABLE"
    _preflight(monkeypatch,tmp_path,data)
    assert repair._root_main(["--preflight"])==2
